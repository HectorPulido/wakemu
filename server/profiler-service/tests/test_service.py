import importlib.util
import json
import os
from pathlib import Path
import signal
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen


SERVICE_PATH = Path(__file__).resolve().parents[1] / "service.py"
SPEC = importlib.util.spec_from_file_location("profiler_service", SERVICE_PATH)
service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(service)


class FakeProcess:
    def __init__(self, wait_result=0):
        self.wait_result = wait_result
        self.signals = []
        self.killed = False

    def wait(self, timeout=None):
        return self.wait_result

    def send_signal(self, value):
        self.signals.append(value)

    def kill(self):
        self.killed = True


class ProfilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name) / "profiles"
        self.profiler = service.Profiler(self.output)

    def tearDown(self):
        self.temp.cleanup()

    def test_world_pid_finds_only_local_game_server_process(self):
        proc = Path(self.temp.name) / "proc"
        proc.mkdir()
        for pid, argv in (
            ("123", [b"python", b"/srv/local_game_server.py", b""]),
            ("124", [b"python", b"/srv/other.py", b""]),
        ):
            entry = proc / pid
            entry.mkdir()
            (entry / "cmdline").write_bytes(b"\0".join(argv))
        self.assertEqual(service.world_pid(proc), 123)

    def test_world_pid_rejects_zero_or_multiple_matches(self):
        proc = Path(self.temp.name) / "proc"
        proc.mkdir()
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            service.world_pid(proc)
        for pid in ("123", "124"):
            entry = proc / pid
            entry.mkdir()
            (entry / "cmdline").write_bytes(b"python\0local_game_server.py\0")
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            service.world_pid(proc)

    def test_process_metrics_parses_proc_stat_and_status(self):
        pid = 2468
        proc = Path(self.temp.name) / "proc"
        process = proc / str(pid)
        process.mkdir(parents=True)
        fields = ["0"] * 20
        fields[0] = "S"
        fields[11] = "300"  # utime, field 14
        fields[12] = "100"  # stime, field 15
        fields[17] = "7"  # num_threads, field 20
        fields[19] = "987654"  # starttime, field 22
        (process / "stat").write_text(f"{pid} (python ) worker) " + " ".join(fields))
        (process / "status").write_text("Name:\tpython\nVmRSS:\t42 kB\nThreads:\t7\n")
        real_path = Path

        def redirected_path(*parts):
            if parts == ("/proc",):
                return proc
            return real_path(*parts)

        with mock.patch.object(
            service, "world_pid", return_value=pid
        ), mock.patch.object(
            service, "Path", side_effect=redirected_path
        ), mock.patch.object(
            service.os, "sysconf", return_value=100
        ):
            metrics = service.process_metrics()
        self.assertEqual(
            metrics,
            {
                "available": True,
                "state": "S",
                "threads": 7,
                "cpu_cumulative_seconds": 4.0,
                "rss_bytes": 42 * 1024,
                "pid": pid,
                "process_start_ticks": "987654",
            },
        )

    def test_process_metrics_reports_unavailable_without_world_process(self):
        with mock.patch.object(
            service, "world_pid", side_effect=RuntimeError("missing")
        ):
            self.assertEqual(service.process_metrics(), {"available": False})

    def test_capture_rejects_invalid_fields_types_and_limits(self):
        invalid = [
            None,
            [],
            {"pid": 1},
            {"seconds": True},
            {"seconds": 4},
            {"seconds": 121},
            {"seconds": 5.0},
            {"mode": "memory"},
        ]
        for request in invalid:
            with self.subTest(request=request), self.assertRaises(ValueError):
                self.profiler.capture(request)

    @mock.patch.object(service, "world_pid", return_value=4321)
    @mock.patch.object(service.subprocess, "Popen")
    def test_capture_uses_fixed_pid_and_sampler_options_and_allows_one_capture(
        self, popen, _pid
    ):
        process = FakeProcess()
        popen.return_value = process
        thread = mock.Mock()
        with mock.patch.object(service.threading, "Thread", return_value=thread):
            try:
                capture = self.profiler.capture({"seconds": 7, "mode": "waits"})
                self.assertEqual(capture["seconds"], 7)
                command = popen.call_args.args[0]
                self.assertEqual(command[:4], ["py-spy", "record", "--pid", "4321"])
                self.assertIn("--duration", command)
                self.assertEqual(command[command.index("--rate") + 1], "25")
                self.assertIn("--threads", command)
                self.assertIn("--nonblocking", command)
                self.assertIn("--idle", command)
                self.assertNotIn("--subprocesses", command)
                with self.assertRaisesRegex(RuntimeError, "already running"):
                    self.profiler.capture({"seconds": 5})
                self.assertEqual(popen.call_count, 1)
            finally:
                popen.call_args.kwargs["stdout"].close()

    @mock.patch.object(service, "world_pid", return_value=4321)
    @mock.patch.object(service.subprocess, "Popen")
    def test_stop_signals_only_sampler_child(self, popen, _pid):
        process = FakeProcess()
        popen.return_value = process
        with mock.patch.object(service.threading, "Thread"):
            try:
                result = self.profiler.capture({"seconds": 5})
                self.assertEqual(
                    self.profiler.stop(),
                    {"stopped": True, "capture_id": result["capture_id"]},
                )
                self.assertEqual(process.signals, [signal.SIGINT])
                self.assertEqual(
                    self.profiler.stop(),
                    {"stopped": True, "capture_id": result["capture_id"]},
                )
                self.assertEqual(process.signals, [signal.SIGINT, signal.SIGINT])
                self.profiler.process = None
                self.assertEqual(self.profiler.stop(), {"stopped": False})
            finally:
                popen.call_args.kwargs["stdout"].close()

    def test_retention_expires_complete_capture_groups_after_one_hour(self):
        now = time.time()
        old_stamp = now - service.RETENTION_SECONDS - 1
        recent_stamp = now - service.RETENTION_SECONDS + 1
        for name, stamp in (
            ("capture-old.speedscope.json", old_stamp),
            ("capture-old.log", old_stamp),
            ("capture-recent.speedscope.json", recent_stamp),
            ("capture-recent.meta.json", recent_stamp),
        ):
            path = self.output / name
            path.write_text("{}")
            os.utime(path, (stamp, stamp))
        self.profiler.prune()
        remaining = {path.name for path in self.output.iterdir()}
        self.assertEqual(
            remaining,
            {"capture-recent.speedscope.json", "capture-recent.meta.json"},
        )

    def test_byte_cap_evicts_oldest_groups_and_reports_recent_truncation(self):
        now = time.time()
        with mock.patch.object(service, "MAX_BYTES", 5), mock.patch.object(
            service.time, "time", return_value=now
        ):
            for name, size, stamp in (
                ("capture-old.log", 3, now - 30),
                ("capture-middle.log", 4, now - 20),
                ("capture-new.log", 4, now - 10),
            ):
                path = self.output / name
                path.write_bytes(b"x" * size)
                os.utime(path, (stamp, stamp))
            self.profiler.prune()
            remaining = {path.name for path in self.output.iterdir()}
            self.assertEqual(remaining, {"capture-new.log"})
            self.assertEqual(self.profiler.retained_bytes, 4)
            self.assertTrue(self.profiler.capacity_truncated)

        with mock.patch.object(service, "MAX_BYTES", 5), mock.patch.object(
            service.time, "time", return_value=now + service.RETENTION_SECONDS + 1
        ):
            self.profiler.prune()
            self.assertFalse(self.profiler.capacity_truncated)
            self.assertEqual(self.profiler.retained_bytes, 0)

    def test_successful_continuous_chunk_chains_and_failed_chunk_waits_for_retry_tick(
        self,
    ):
        destination = self.output / "capture-current.speedscope.json"
        destination.write_text("{}")
        log = open(self.output / "capture-current.log", "w")
        process = FakeProcess(wait_result=0)
        self.profiler.enabled = True
        self.profiler.process = process
        self.profiler.current = {
            "capture_id": "capture-current",
            "artifact": destination.name,
            "mode": "waits",
            "seconds": service.CHUNK_SECONDS,
            "started_at": time.time() - service.CHUNK_SECONDS,
            "continuous": True,
        }
        with mock.patch.object(self.profiler, "capture") as capture:
            self.profiler.finish(process, log, destination)
        capture.assert_called_once_with(
            {"seconds": service.CHUNK_SECONDS, "mode": "waits"}, continuous=True
        )
        self.assertIsNone(self.profiler.current)
        self.assertEqual(self.profiler.last["return_code"], 0)
        self.assertTrue((self.output / "capture-current.meta.json").is_file())

        failed = FakeProcess(wait_result=1)
        self.profiler.process = failed
        self.profiler.current = {
            "capture_id": "capture-failed",
            "artifact": "capture-failed.speedscope.json",
            "mode": "waits",
            "seconds": service.CHUNK_SECONDS,
            "started_at": time.time() - service.CHUNK_SECONDS,
            "continuous": True,
        }
        failed_log = open(self.output / "capture-failed.log", "w")
        failed_destination = self.output / "capture-failed.speedscope.json"
        with mock.patch.object(self.profiler, "capture") as capture:
            self.profiler.finish(failed, failed_log, failed_destination)
        capture.assert_not_called()
        self.assertIn("code 1", self.profiler.last_error)

    def test_enabled_run_records_timeline_and_starts_waits_chunk(self):
        self.profiler.enabled = True
        self.profiler.shutdown.wait = mock.Mock(side_effect=[False, True])
        with mock.patch.object(
            service, "process_metrics", return_value={"available": False}
        ), mock.patch.object(self.profiler, "capture") as capture:
            self.profiler.run()
        capture.assert_called_once_with(
            {"seconds": service.CHUNK_SECONDS, "mode": "waits"}, continuous=True
        )
        timelines = list(self.output.glob("timeline-*.jsonl"))
        self.assertEqual(len(timelines), 1)
        row = json.loads(timelines[0].read_text().splitlines()[0])
        self.assertTrue(row["continuous_enabled"])
        self.assertEqual(row["world"], {"available": False})


class HandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name) / "profiles"
        cls.profiler = service.Profiler(cls.output)
        handler = type("TestHandler", (service.Handler,), {"profiler": cls.profiler})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data is not None else {},
        )
        try:
            response = urlopen(request)
        except HTTPError as error:
            response = error
        result = response.code, response.headers.get("Content-Type"), response.read()
        response.close()
        return result

    def test_report_endpoint_serves_json_and_missing_or_invalid_report_is_404(self):
        metrics = Path(self.temp.name) / "report.json"
        with mock.patch.object(service, "METRICS", metrics):
            code, content_type, body = self.request("GET", "/report")
            self.assertEqual(
                (code, json.loads(body)),
                (404, {"error": "No performance report has been published yet"}),
            )
            metrics.write_text("{bad json")
            self.assertEqual(self.request("GET", "/report")[0], 404)
            metrics.write_text('{"samples": 3}')
            code, content_type, body = self.request("GET", "/report")
        self.assertEqual(code, 200)
        self.assertEqual(content_type, "application/json")
        self.assertEqual(json.loads(body), {"samples": 3})

    def test_artifact_routes_reject_traversal_and_symlinks(self):
        outside = Path(self.temp.name) / "secret"
        outside.write_text("secret")
        (self.output / "capture-good.log").write_text("ok")
        (self.output / "capture-link.log").symlink_to(outside)
        self.assertEqual(self.request("GET", "/artifacts/../secret")[0], 400)
        self.assertEqual(self.request("GET", "/artifacts/%2e%2e%2fsecret")[0], 400)
        self.assertEqual(self.request("GET", "/artifacts/capture-link.log")[0], 404)
        code, content_type, body = self.request("GET", "/artifacts/capture-good.log")
        self.assertEqual((code, content_type, body), (200, "text/plain", b"ok"))

    def test_post_body_size_limit_and_input_errors_return_400(self):
        request = Request(
            self.base + "/capture",
            data=b"x" * 4097,
            method="POST",
            headers={"Content-Length": "4097"},
        )
        try:
            response = urlopen(request)
        except HTTPError as error:
            response = error
        self.assertEqual(response.code, 400)
        response.close()
        with mock.patch.object(
            self.profiler, "capture", side_effect=ValueError("bad input")
        ):
            code, _, body = self.request("POST", "/capture", {"seconds": 5})
        self.assertEqual((code, json.loads(body)), (400, {"error": "bad input"}))


if __name__ == "__main__":
    unittest.main()
