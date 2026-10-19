"""Process-wide bounded combat work and reader-owned diagnostic delivery."""

from concurrent.futures import ThreadPoolExecutor
from contextvars import Context
from itertools import islice
from queue import Empty, Full, Queue
from threading import Lock


class BackgroundDiagnostics:
    def __init__(self, capacity=128):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Invalid background diagnostic capacity")
        self.queue = Queue(maxsize=capacity)
        self.lock = Lock()
        self.dropped = 0

    def put(self, owner, fields):
        """Retain bounded metadata, never a runtime or a worker callback."""
        remaining = [256]

        def bounded(value, depth=0):
            remaining[0] -= 1
            if remaining[0] < 0 or depth > 5:
                return "[metadata omitted]"
            if value is None or type(value) in (bool, int, float):
                return value
            if type(value) is str:
                return value[:512]
            if type(value) is dict:
                return {
                    str(key)[:128]: bounded(item, depth + 1)
                    for key, item in islice(value.items(), 32)
                    if type(key) in (str, int)
                }
            if type(value) in (list, tuple):
                return [bounded(item, depth + 1) for item in value[:32]]
            return "[non-metadata value omitted]"

        try:
            self.queue.put_nowait((owner, bounded(fields)))
        except Full:
            with self.lock:
                self.dropped += 1

    def drain(self, owner):
        result = []
        while True:
            try:
                expected, fields = self.queue.get_nowait()
            except Empty:
                break
            if expected == owner:
                result.append(fields)
        with self.lock:
            dropped, self.dropped = self.dropped, 0
        return tuple(result), dropped


class BackgroundWork:
    """No unbounded executor backlog; one active operation per opaque key."""

    def __init__(self, max_jobs=2, max_workers=None):
        if type(max_jobs) is not int or max_jobs < 1:
            raise ValueError("Invalid background combat work capacity")
        max_workers = max_jobs if max_workers is None else max_workers
        if type(max_workers) is not int or not 1 <= max_workers <= max_jobs:
            raise ValueError("Invalid background combat worker capacity")
        self.max_jobs = max_jobs
        self.max_workers = max_workers
        self.lock = Lock()
        self.jobs = {}
        self.cancelled = set()
        self.executor = None

    def submit(self, key, operation):
        with self.lock:
            if key in self.jobs:
                return "duplicate"
            if len(self.jobs) >= self.max_jobs:
                return "capacity"
            if self.executor is None:
                self.executor = ThreadPoolExecutor(
                    max_workers=self.max_workers, thread_name_prefix="native-combat"
                )
            self.jobs[key] = operation
            try:
                self.executor.submit(self._run, key, operation)
            except BaseException:
                self.jobs.pop(key, None)
                raise
        return "submitted"

    def status(self, key):
        with self.lock:
            if key in self.jobs:
                return "duplicate"
            if len(self.jobs) >= self.max_jobs:
                return "capacity"
        return None

    def _run(self, key, operation):
        try:
            # A worker must not inherit a reader's request/observation scope.
            with self.lock:
                cancelled = key in self.cancelled
            if not cancelled:
                Context().run(operation)
        finally:
            with self.lock:
                if self.jobs.get(key) is operation:
                    self.jobs.pop(key, None)
                    self.cancelled.discard(key)

    def cancel(self, key):
        with self.lock:
            operation = self.jobs.get(key)
            if operation is not None:
                self.cancelled.add(key)
        if operation is not None:
            operation.cancel()
            return True
        return False

    def shutdown(self):
        with self.lock:
            jobs = tuple(self.jobs.values())
            self.cancelled.update(self.jobs)
            executor = self.executor
        for operation in jobs:
            operation.cancel()
        if executor is not None:
            executor.shutdown(wait=True)


# This module belongs to the stable engine, not a hashed SDK package. A live
# SDK reload therefore cannot create an additional pool or bypass its bound.
NATIVE_WORK = BackgroundWork(max_jobs=16, max_workers=2)
