"""Session-independent retry-safe persistence callbacks.

Redis Scheduler owns distributed leases. This process deduplicates completed
occurrences; a crash before reply may safely repeat a durable journal flush.
"""
import threading
import time

ALLOWED_TASKS = frozenset(("positions_flush",))


class GlobalTasks:
    def __init__(self, callbacks, *, clock=time.monotonic, retention_seconds=604800):
        if set(callbacks) - ALLOWED_TASKS or any(
            not callable(c) for c in callbacks.values()
        ):
            raise ValueError("Unknown or invalid global callback")
        self.callbacks = dict(callbacks)
        self.clock = clock
        self.retention_seconds = retention_seconds
        self.completed = {}
        self.lock = threading.RLock()

    def names(self):
        return sorted(self.callbacks)

    def run(self, name, request_id):
        if name not in self.callbacks:
            raise ValueError("Unknown global task")
        if not isinstance(request_id, str) or not request_id or len(request_id) > 200:
            raise ValueError("Global task requires a bounded occurrence ID")
        if not request_id.startswith(name + ":"):
            raise ValueError("Occurrence does not belong to task")
        with self.lock:
            now = self.clock()
            self.completed = {k: v for k, v in self.completed.items() if v[0] > now}
            key = (name, request_id)
            if key in self.completed:
                return dict(self.completed[key][1], deduplicated=True)
            self.callbacks[name]()
            result = dict(task=name, request_id=request_id, status="completed")
            self.completed[key] = (now + self.retention_seconds, result)
            return dict(result, deduplicated=False)
