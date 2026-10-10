"""Periodic bounded performance export outside gameplay threads and locks."""
import json
import os
import threading
import time


def write_report(profiler, path, *, lag_seconds=0.0):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = profiler.snapshot()
    payload["monitor_lag_seconds"] = max(0.0, lag_seconds)
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf8") as stream:
            json.dump(payload, stream, separators=(",", ":"), allow_nan=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def start_monitor(profiler, path, stopping, *, interval=30.0):
    if interval < 1:
        raise ValueError("Performance export interval must be at least one second")

    def run():
        expected = time.monotonic() + interval
        while not stopping.wait(interval):
            lag = max(0.0, time.monotonic() - expected)
            profiler.observe("diagnostics.monitor_lag", lag, 0.0)
            try:
                write_report(profiler, path, lag_seconds=lag)
            except Exception:
                # Disk faults must not affect gameplay or recursively log.
                profiler.observe("diagnostics.report_failure", 0.0, 0.0, error=True)
            expected = time.monotonic() + interval

    worker = threading.Thread(target=run, name="performance-report-writer", daemon=True)
    worker.start()
    return worker
