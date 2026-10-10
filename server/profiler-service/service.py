"""Optional external sampler; never controls the world process."""
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

OUTPUT = Path(os.environ.get("PROFILER_OUTPUT", "/profiles"))
METRICS = Path(os.environ.get("PROFILER_METRICS", "/metrics/performance-latest.json"))
RATE = 25
RETENTION_SECONDS = 3600
MAX_BYTES = int(os.environ.get("PROFILER_MAX_BYTES", str(1024**3)))
CHUNK_SECONDS = 60
TIMELINE_SECONDS = 5


def world_pid(proc_root=Path("/proc")):
    matches = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            args = (entry / "cmdline").read_bytes().split(b"\0")
            if any(
                Path(os.fsdecode(arg)).name == "local_game_server.py"
                for arg in args
                if arg
            ):
                matches.append(int(entry.name))
        except (OSError, ValueError):
            continue
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one world Python process")
    return matches[0]


def process_metrics():
    try:
        pid = world_pid()
        stat = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
        status = (Path("/proc") / str(pid) / "status").read_text().splitlines()
        rss = next(
            (
                int(line.split()[1]) * 1024
                for line in status
                if line.startswith("VmRSS:")
            ),
            0,
        )
        return {
            "available": True,
            "state": stat[0],
            "threads": int(stat[17]),
            "cpu_cumulative_seconds": (int(stat[11]) + int(stat[12]))
            / os.sysconf("SC_CLK_TCK"),
            "rss_bytes": rss,
            "pid": pid,
            "process_start_ticks": stat[19] if len(stat) > 19 else None,
        }
    except (OSError, RuntimeError, ValueError, IndexError):
        return {"available": False}


class Profiler:
    def __init__(self, output=OUTPUT, continuous=False):
        self.output = output
        output.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(output, 0o700)
        self.lock = threading.Lock()
        self.process = None
        self.current = None
        self.last = None
        self.enabled = continuous
        self.enabled_at = time.time()
        self.shutdown = threading.Event()
        self.last_error = None
        self.capacity_truncated = False
        self.last_capacity_eviction_at = None
        self.retained_bytes = 0
        self.active_bytes = 0
        self.prune()
        if continuous:
            threading.Thread(target=self.run, daemon=True).start()

    def prune(self):
        cutoff = time.time() - RETENTION_SECONDS
        active = self.current["capture_id"] if self.current else None
        groups = {}
        active_bytes = 0
        for path in self.output.iterdir():
            if (
                path.is_symlink()
                or not path.is_file()
                or not path.name.startswith(("capture-", "timeline-"))
            ):
                continue
            info = path.stat()
            if active and path.name.startswith(active + "."):
                active_bytes += info.st_size
                continue
            group = path.name.split(".")[0]
            groups.setdefault(group, []).append((info.st_mtime, info.st_size, path))
        retained = []
        for files in groups.values():
            if max(row[0] for row in files) < cutoff:
                for _, _, path in files:
                    path.unlink(missing_ok=True)
            else:
                retained.append(
                    (min(row[0] for row in files), sum(row[1] for row in files), files)
                )
        total = sum(size for _, size, _ in retained) + active_bytes
        self.capacity_truncated = bool(
            self.last_capacity_eviction_at and self.last_capacity_eviction_at > cutoff
        )
        for _, size, files in sorted(retained):
            if total <= MAX_BYTES:
                break
            for _, _, path in files:
                path.unlink(missing_ok=True)
            total -= size
            self.capacity_truncated = True
            self.last_capacity_eviction_at = time.time()
        self.retained_bytes = total
        self.active_bytes = active_bytes
        if active_bytes > MAX_BYTES:
            self.capacity_truncated = True
            self.last_error = "Active capture exceeds byte cap; finalizing early"
            self.process.send_signal(signal.SIGINT)

    def status(self):
        with self.lock:
            metadata = []
            for path in self.output.glob("capture-*.meta.json"):
                try:
                    metadata.append(json.loads(path.read_text()))
                except (OSError, ValueError):
                    pass
            successful = sorted(
                (
                    row
                    for row in metadata
                    if row.get("return_code") == 0
                    and (self.output / row.get("artifact", "")).is_file()
                ),
                key=lambda row: row["started_at"],
            )
            gaps = []
            for previous, following in zip(successful, successful[1:]):
                gap = following["started_at"] - previous["finished_at"]
                if gap > 2:
                    gaps.append({"started_at": previous["finished_at"], "seconds": gap})
            if (
                self.current
                and successful
                and self.current["started_at"] - successful[-1]["finished_at"] > 2
            ):
                gaps.append(
                    {
                        "started_at": successful[-1]["finished_at"],
                        "seconds": self.current["started_at"]
                        - successful[-1]["finished_at"],
                    }
                )
            coverage_end = (
                self.current["started_at"]
                if self.current
                else (successful[-1]["finished_at"] if successful else self.enabled_at)
            )
            if self.enabled and not self.process and time.time() - coverage_end > 2:
                gaps.append(
                    {
                        "started_at": coverage_end,
                        "seconds": time.time() - coverage_end,
                        "ongoing": True,
                    }
                )
            return {
                "running": self.process is not None,
                "continuous_enabled": self.enabled,
                "current": self.current,
                "last": self.last,
                "sample_rate": RATE,
                "retention_seconds": RETENTION_SECONDS,
                "max_bytes": MAX_BYTES,
                "retained_bytes": self.retained_bytes,
                "active_bytes": self.active_bytes,
                "capacity_truncated": self.capacity_truncated,
                "degraded": self.capacity_truncated or bool(self.last_error),
                "last_error": self.last_error,
                "coverage_started_at": successful[0]["started_at"]
                if successful
                else None,
                "coverage_finished_at": successful[-1]["finished_at"]
                if successful
                else None,
                "completed_chunks": len(successful),
                "gaps": gaps,
                "world": process_metrics(),
            }

    def enable(self):
        with self.lock:
            self.enabled = True
            self.enabled_at = time.time()
        return {
            "continuous_enabled": True,
            "mode": "waits",
            "chunk_seconds": CHUNK_SECONDS,
        }

    def run(self):
        """Persist bounded history and rotate the external sampler for the service lifetime."""
        while not self.shutdown.wait(TIMELINE_SECONDS):
            try:
                now = time.time()
                row = {"recorded_at": now, "world": process_metrics()}
                try:
                    row["metrics"] = json.loads(METRICS.read_text())
                    row["metrics_file_updated_at"] = METRICS.stat().st_mtime
                    row["metrics_age_seconds"] = max(
                        0, now - row["metrics_file_updated_at"]
                    )
                except (OSError, ValueError):
                    row["metrics"] = None
                with self.lock:
                    row["continuous_enabled"] = self.enabled
                    row["capture_id"] = (
                        self.current["capture_id"] if self.current else None
                    )
                path = self.output / ("timeline-" + str(int(now // 60)) + ".jsonl")
                with path.open("a") as stream:
                    stream.write(json.dumps(row, separators=(",", ":")) + "\n")
                os.chmod(path, 0o600)
                with self.lock:
                    self.prune()
                    should_start = self.enabled and self.process is None
                if should_start:
                    self.capture(
                        {"seconds": CHUNK_SECONDS, "mode": "waits"}, continuous=True
                    )
            except (OSError, RuntimeError, ValueError) as exc:
                self.last_error = str(exc)

    def capture(self, request, continuous=False):
        if not isinstance(request, dict) or set(request) - {"seconds", "mode"}:
            raise ValueError("Only seconds and mode are accepted")
        seconds = request.get("seconds", 30)
        mode = request.get("mode", "cpu")
        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, int)
            or not 5 <= seconds <= 120
        ):
            raise ValueError("seconds must be an integer between 5 and 120")
        if mode not in ("cpu", "waits"):
            raise ValueError("mode must be cpu or waits")
        with self.lock:
            if self.process is not None:
                if self.enabled and not continuous:
                    return dict(
                        self.current,
                        continuous_enabled=True,
                        note="Continuous recording already covers this interval",
                    )
                raise RuntimeError("A capture is already running")
            pid = world_pid()
            capture_id = "capture-" + str(time.time_ns())
            destination = self.output / (capture_id + ".speedscope.json")
            log_path = self.output / (capture_id + ".log")
            command = [
                "py-spy",
                "record",
                "--pid",
                str(pid),
                "--duration",
                str(seconds),
                "--rate",
                str(RATE),
                "--threads",
                "--nonblocking",
                "--format",
                "speedscope",
                "--output",
                str(destination),
            ]
            if mode == "waits":
                command.append("--idle")
            log = open(log_path, "xb")
            os.chmod(log_path, 0o600)
            try:
                process = subprocess.Popen(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            except Exception:
                log.close()
                raise
            self.process = process
            self.current = {
                "capture_id": capture_id,
                "mode": mode,
                "seconds": seconds,
                "started_at": time.time(),
                "artifact": destination.name,
                "continuous": continuous,
                "world": process_metrics(),
                "interpretation": "sampled active stacks"
                if mode == "cpu"
                else "sampled stacks including idle threads",
            }
            threading.Thread(
                target=self.finish, args=(process, log, destination), daemon=True
            ).start()
            return dict(self.current)

    def finish(self, process, log, destination):
        try:
            return_code = process.wait(timeout=140)
        except subprocess.TimeoutExpired:
            process.kill()
            return_code = process.wait()
        finally:
            log.close()
        if destination.exists():
            os.chmod(destination, 0o600)
        with self.lock:
            self.last = dict(
                self.current, return_code=return_code, finished_at=time.time()
            )
            metadata = self.output / (self.current["capture_id"] + ".meta.json")
            metadata.write_text(json.dumps(self.last))
            os.chmod(metadata, 0o600)
            self.current = None
            self.process = None
            self.prune()
            resume = self.enabled and return_code == 0
            self.last_error = (
                None
                if return_code == 0
                else "Sampler exited with code " + str(return_code)
            )
        if resume:
            try:
                self.capture(
                    {"seconds": CHUNK_SECONDS, "mode": "waits"}, continuous=True
                )
            except (RuntimeError, OSError) as exc:
                self.last_error = str(exc)

    def stop(self):
        with self.lock:
            self.enabled = False
            if self.process is None:
                return {"stopped": False}
            # SIGINT allows py-spy to finalize a partial capture. Only the child is targeted.
            self.process.send_signal(signal.SIGINT)
            return {"stopped": True, "capture_id": self.current["capture_id"]}


class Handler(BaseHTTPRequestHandler):
    profiler = None

    def log_message(self, *args):
        pass

    def respond(self, code, data):
        payload = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            return self.respond(200, {"ok": True})
        if path == "/status":
            return self.respond(200, self.profiler.status())
        if path == "/report":
            try:
                return self.respond(200, json.loads(METRICS.read_text()))
            except (OSError, ValueError):
                return self.respond(
                    404, {"error": "No performance report has been published yet"}
                )
        if path == "/artifacts":
            return self.respond(
                200,
                {
                    "artifacts": sorted(
                        p.name
                        for p in self.profiler.output.iterdir()
                        if p.name.startswith(("capture-", "timeline-"))
                        if p.is_file()
                    )
                },
            )
        if path.startswith("/artifacts/"):
            name = path[len("/artifacts/") :]
            if (
                not name
                or Path(name).name != name
                or not name.startswith(("capture-", "timeline-"))
                or not name.endswith(
                    (".speedscope.json", ".log", ".meta.json", ".jsonl")
                )
            ):
                return self.respond(400, {"error": "Invalid artifact name"})
            destination = self.profiler.output / name
            if destination.is_symlink() or not destination.is_file():
                return self.respond(404, {"error": "Artifact not found"})
            payload = destination.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json" if name.endswith(".json") else "text/plain",
            )
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.respond(404, {"error": "Unknown endpoint"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 4096:
                raise ValueError("Invalid request size")
            request = json.loads(self.rfile.read(length) or b"{}")
            path = urlsplit(self.path).path
            if path == "/start":
                return self.respond(200, self.profiler.enable())
            if path == "/capture":
                return self.respond(202, self.profiler.capture(request))
            if path == "/stop":
                return self.respond(200, self.profiler.stop())
            self.respond(404, {"error": "Unknown endpoint"})
        except (ValueError, TypeError) as exc:
            self.respond(400, {"error": str(exc)})
        except RuntimeError as exc:
            self.respond(409, {"error": str(exc)})
        except OSError:
            self.respond(503, {"error": "Sampler could not start"})


if __name__ == "__main__":
    os.umask(0o077)
    Handler.profiler = Profiler(continuous=True)
    server = ThreadingHTTPServer(("0.0.0.0", 8092), Handler)

    def terminate(_signal, _frame):
        Handler.profiler.shutdown.set()
        Handler.profiler.stop()
        deadline = time.monotonic() + 8
        while Handler.profiler.process is not None and time.monotonic() < deadline:
            time.sleep(0.05)
        if Handler.profiler.process is not None:
            Handler.profiler.process.kill()
        server.server_close()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    server.serve_forever()
