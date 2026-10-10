"""Regression gates for diagnostic publication and gameplay isolation."""
import ast
import json
from pathlib import Path
from urllib.error import URLError
import tempfile
import threading
from unittest import TestCase
from unittest.mock import Mock, patch

from wakfu_server.storage.performance_commands import (
    execute_profile_command,
    external_control,
)
from wakfu_server.storage.performance_monitor import start_monitor, write_report
from wakfu_server.storage.performance_profiler import PerformanceProfiler
from wakfu_server.storage.request_diagnostics import RequestTrace


class PerformanceAcceptanceTests(TestCase):
    def test_sampling_early_stop_keeps_bounded_retention_and_clears_active_state(self):
        import time

        profiler = PerformanceProfiler(retention=2)
        with tempfile.TemporaryDirectory() as directory:
            for _ in range(4):
                stopping = threading.Event()
                stopping.set()
                state = dict(
                    duration=30,
                    interval=0.05,
                    stop=stopping,
                    output_dir=Path(directory),
                    started_at=time.time(),
                )
                profiler._sampling = state
                profiler._sample(state)
                self.assertFalse(profiler.status()["sampling"])
            paths = list(Path(directory).glob("performance-profile-*.json"))
            self.assertEqual(len(paths), 2)
            for path in paths:
                self.assertEqual(json.loads(path.read_text())["rounds"], 0)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_sampling_export_error_clears_active_state_and_omits_exception_contents(
        self,
    ):
        import time

        profiler = PerformanceProfiler()
        stopping = threading.Event()
        stopping.set()
        with tempfile.TemporaryDirectory() as directory:
            state = dict(
                duration=30,
                interval=0.05,
                stop=stopping,
                output_dir=Path(directory),
                started_at=time.time(),
            )
            profiler._sampling = state
            with patch(
                "wakfu_server.storage.performance_profiler.os.open",
                side_effect=OSError("private database password"),
            ):
                profiler._sample(state)
            status = profiler.status()
            self.assertFalse(status["sampling"])
            self.assertEqual(status["last_sample"]["error"], "OSError")
            self.assertNotIn("password", json.dumps(status))

    def test_capture_uses_external_control_with_default_cpu_and_explicit_waits(self):
        profiler, control = Mock(), Mock()
        execute_profile_command(profiler, "!perfil iniciar", control=control)
        control.assert_called_once_with("iniciar", {"seconds": 30.0, "mode": "cpu"})
        control.reset_mock()
        execute_profile_command(profiler, "!perfil iniciar 12 waits", control=control)
        control.assert_called_once_with("iniciar", {"seconds": 12.0, "mode": "waits"})
        self.assertEqual(profiler.mock_calls, [])

    def test_stop_uses_external_control_without_starting_internal_sampler(self):
        profiler, control = Mock(), Mock()
        execute_profile_command(profiler, "!perfil detener", control=control)
        control.assert_called_once_with("detener", {})
        self.assertEqual(profiler.mock_calls, [])

    def test_aggregate_report_remains_available_when_external_service_is_off(self):
        profiler = PerformanceProfiler()
        profiler.observe("combat.refresh", 0.01)
        unavailable = Mock(side_effect=ValueError("service unavailable"))
        report = execute_profile_command(
            profiler, "!perfil informe", control=unavailable
        )
        self.assertIn("combat.refresh", report)
        unavailable.assert_not_called()
        with self.assertRaisesRegex(ValueError, "service unavailable"):
            execute_profile_command(profiler, "!perfil estado", control=unavailable)

    def test_external_control_has_fixed_url_bounded_read_and_timeout(self):
        response = Mock()
        response.read.return_value = b'{"active":false}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch(
            "wakfu_server.storage.performance_commands.urlopen", return_value=response
        ) as opened:
            self.assertEqual(external_control("estado"), {"active": False})
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, "http://profiler:8092/status")
        self.assertEqual(request.method, "GET")
        self.assertEqual(opened.call_args.kwargs["timeout"], 1.0)
        response.read.assert_called_once_with(65536)
        with patch("wakfu_server.storage.performance_commands.urlopen") as opened:
            with self.assertRaises(KeyError):
                external_control("http://attacker.example/")
            opened.assert_not_called()

    def test_external_failure_does_not_expose_transport_exception_details(self):
        with patch(
            "wakfu_server.storage.performance_commands.urlopen",
            side_effect=URLError("private credential"),
        ):
            with self.assertRaises(ValueError) as caught:
                external_control("estado")
        self.assertNotIn("credential", str(caught.exception))
        self.assertIn("apagado", str(caught.exception))

    def test_periodic_report_atomically_replaces_one_private_file(self):
        profiler = PerformanceProfiler()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            for count in range(3):
                profiler.observe("combat.refresh", 0.001)
                write_report(profiler, path, lag_seconds=-1)
            payload = json.loads(path.read_text())
            self.assertEqual(payload["features"][0]["count"], 3)
            self.assertEqual(payload["monitor_lag_seconds"], 0)
            self.assertEqual(list(path.parent.iterdir()), [path])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_report_replace_failure_preserves_previous_report_and_cleans_temporary(
        self,
    ):
        profiler = PerformanceProfiler()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            write_report(profiler, path)
            previous = path.read_bytes()
            with patch(
                "wakfu_server.storage.performance_monitor.os.replace",
                side_effect=OSError("disk"),
            ):
                with self.assertRaises(OSError):
                    write_report(profiler, path)
            self.assertEqual(path.read_bytes(), previous)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_stopped_monitor_does_not_start_sampling_or_export(self):
        stopping = threading.Event()
        stopping.set()
        profiler = Mock()
        with tempfile.TemporaryDirectory() as directory:
            worker = start_monitor(
                profiler, Path(directory) / "latest.json", stopping, interval=1
            )
            worker.join(1)
            self.assertFalse(worker.is_alive())
            profiler.assert_not_called()
            self.assertEqual(profiler.mock_calls, [])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_chat_rejects_unbounded_sampling_and_extra_arguments(self):
        profiler = Mock()
        for text in (
            "!perfil iniciar nan",
            "!perfil iniciar inf",
            "!perfil iniciar 121",
            "!perfil iniciar 4",
            "!perfil iniciar 30 target",
            "!perfil informe secrets",
            "!perfil detener target",
            "!perfil reiniciar target",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                execute_profile_command(profiler, text, Path("unused"))
        self.assertEqual(profiler.mock_calls, [])

    def test_chat_report_is_bounded_to_six_fixed_feature_labels(self):
        profiler = PerformanceProfiler()
        for index in range(12):
            profiler.observe("combat.feature" + str(index), index + 1)
        report = execute_profile_command(profiler, "!perfil informe", Path("unused"))
        self.assertEqual(len(report.splitlines()), 7)
        self.assertIn("combat.feature11", report)
        self.assertNotIn("combat.feature0:", report)

    def test_request_finish_counts_once_and_ignores_custom_sensitive_action(self):
        with patch("wakfu_server.performance_profiler.PROFILER") as profiler:
            request = RequestTrace(
                sink=Mock(),
                opcode=999999,
                service=1,
                connection_id="private-player",
                snapshot=lambda: {},
                action="private-player-token",
                clock=Mock(side_effect=[1, 2, 3]),
            )
            request.finish(status="failed")
            request.finish()
        profiler.observe.assert_called_once()
        self.assertEqual(profiler.observe.call_args.args[0], "request.other")
        self.assertTrue(profiler.observe.call_args.kwargs["error"])

    def test_connection_send_failure_releases_lock_and_preserves_error(self):
        source = Path(__file__).parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        node = next(
            item
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "Connection"
        )
        module = ast.Module(body=[node], type_ignores=[])
        namespace = {"threading": threading, "PROFILER": PerformanceProfiler()}
        exec(compile(module, str(source), "exec"), namespace)
        error = OSError("original send failed")
        socket = Mock()
        socket.sendall.side_effect = error
        connection = namespace["Connection"](socket)
        with self.assertRaises(OSError) as caught:
            connection.sendall(b"private packet")
        self.assertIs(caught.exception, error)
        self.assertTrue(connection.write_lock.acquire(blocking=False))
        connection.write_lock.release()
        rows = {
            row["name"]: row for row in namespace["PROFILER"].snapshot()["features"]
        }
        self.assertEqual(rows["network.send"]["errors"], 1)

    def test_game_server_admin_gate_precedes_profile_execution_and_background_wait_is_outside_span(
        self,
    ):
        source = Path(__file__).parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        command = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "execute_test_command"
        )
        branch = next(
            node
            for node in ast.walk(command)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "command == '!perfil'"
        )
        guard = next(node for node in branch.body if isinstance(node, ast.If))
        self.assertIn("is_admin", ast.unparse(guard.test))
        self.assertTrue(any(isinstance(node, ast.Raise) for node in guard.body))
        execution = next(
            node
            for node in ast.walk(branch)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "execute_profile_command"
        )
        self.assertLess(guard.lineno, execution.lineno)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "grow_planted_resources"
        )
        loop = function.body[0]
        self.assertIsInstance(loop, ast.While)
        self.assertIn("STOPPING.wait", ast.unparse(loop.test))
        self.assertIsInstance(loop.body[0], ast.With)
