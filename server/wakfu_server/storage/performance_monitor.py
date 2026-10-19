"""Periodic bounded performance export outside gameplay threads and locks."""
import json
import os
import threading
import time


def write_report(profiler, path, *, lag_seconds=0.0, gc_monitor=None):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = profiler.snapshot()
    payload["monitor_lag_seconds"] = max(0.0, lag_seconds)
    if gc_monitor is None:
        from .gc_pause_monitor import MONITOR

        gc_monitor = MONITOR
    payload["gc_pause_history"] = gc_monitor.history_snapshot()
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
    from .gc_pause_monitor import MONITOR

    MONITOR.install()

    def run():
        try:
            expected = time.monotonic() + interval
            while not stopping.wait(interval):
                lag = max(0.0, time.monotonic() - expected)
                MONITOR.drain(profiler)
                profiler.observe("diagnostics.monitor_lag", lag, 0.0)
                try:
                    write_report(profiler, path, lag_seconds=lag, gc_monitor=MONITOR)
                except Exception:
                    # Disk faults must not affect gameplay or recursively log.
                    profiler.observe("diagnostics.report_failure", 0.0, 0.0, error=True)
                expected = time.monotonic() + interval
        finally:
            MONITOR.uninstall()

    worker = threading.Thread(target=run, name="performance-report-writer", daemon=True)
    worker.start()
    return worker
