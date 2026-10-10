"""Capture slow persistence thread stacks without acquiring gameplay locks."""
from contextlib import contextmanager
import faulthandler
import threading


class CheckpointWatchdog:
    def __init__(self, path, *, timeout=5.0, backend=faulthandler):
        if timeout <= 0:
            raise ValueError("Checkpoint watchdog timeout must be positive")
        self.stream = path.open("ab", buffering=0)
        self.timeout = timeout
        self.backend = backend
        self.lock = threading.Lock()
        self.active = 0
        self.armed = False

    @contextmanager
    def watch(self):
        with self.lock:
            if self.active == 0:
                # The native watchdog can dump threads while Python's GIL or
                # logging writer is blocked. Never terminate the process.
                try:
                    self.backend.dump_traceback_later(
                        self.timeout, repeat=False, file=self.stream, exit=False
                    )
                    self.armed = True
                except (OSError, RuntimeError, ValueError):
                    self.armed = False
            self.active += 1
        try:
            yield
        finally:
            with self.lock:
                self.active -= 1
                if self.active == 0 and self.armed:
                    try:
                        self.backend.cancel_dump_traceback_later()
                    except (OSError, RuntimeError, ValueError):
                        pass  # Diagnostics must not override a committed save.
                    finally:
                        self.armed = False

    def close(self):
        with self.lock:
            if self.active:
                raise RuntimeError("Cannot close an active checkpoint watchdog")
            if self.armed:
                try:
                    self.backend.cancel_dump_traceback_later()
                except (OSError, RuntimeError, ValueError):
                    pass
                finally:
                    self.armed = False
            self.stream.close()
