"""Bounded diagnostic logging; filesystem latency never owns gameplay locks."""
import json
import threading
import time
from collections import deque


class AsyncDiagnosticLog:
    def __init__(self, path, *, capacity=8192, critical_reserve=512, writer=None):
        if capacity < 1 or not 0 <= critical_reserve < capacity:
            raise ValueError("Invalid diagnostic log capacity")
        self.path = path
        self.capacity = capacity
        self.reserve = critical_reserve
        self.writer = writer or self._write
        self.condition = threading.Condition()
        self.pending = deque()
        self.queued_rows = 0
        self.active = False
        self.stopping = False
        self.dropped = 0
        self.write_errors = 0
        self.thread = threading.Thread(
            target=self._run, name="wakfu-diagnostic-writer", daemon=True
        )
        self.thread.start()

    def _write(self, batches):
        with self.path.open("a") as stream:
            stream.writelines(json.dumps(row) + "\n" for row in batches)

    @staticmethod
    def _critical(rows):
        return any(
            row.get("event", "").endswith(("_failed", "_rejected", "_exception"))
            or row.get("event", "").startswith("server_shutdown")
            for row in rows
        )

    def enqueue(self, rows):
        # Callers already redact and detach diagnostic rows. Keep each request
        # batch contiguous, and preserve order among all retained batches.
        rows = tuple(rows)
        if not rows:
            return True
        critical = self._critical(rows)
        with self.condition:
            limit = self.capacity if critical else self.capacity - self.reserve
            if critical and self.queued_rows + len(rows) > limit:
                kept = deque()
                while self.pending:
                    batch, important = self.pending.popleft()
                    if not important and self.queued_rows + len(rows) > limit:
                        self.queued_rows -= len(batch)
                        self.dropped += len(batch)
                    else:
                        kept.append((batch, important))
                self.pending = kept
            if self.stopping or self.queued_rows + len(rows) > limit:
                self.dropped += len(rows)
                return False
            self.pending.append((rows, critical))
            self.queued_rows += len(rows)
            self.condition.notify()
            return True

    def _run(self):
        while True:
            with self.condition:
                while not self.pending and not self.stopping:
                    self.condition.wait()
                if not self.pending:
                    return
                rows, _ = self.pending.popleft()
                self.queued_rows -= len(rows)
                self.active = True
                dropped, errors = self.dropped, self.write_errors
                self.dropped = self.write_errors = 0
            original_count = len(rows)
            if dropped or errors:
                rows = (
                    {
                        "event": "diagnostic_log_overflow",
                        "dropped_rows": dropped,
                        "write_errors": errors,
                    },
                    *rows,
                )
            try:
                self.writer(rows)
            except Exception:
                # Diagnostics cannot change authoritative state or recursively
                # log into their own failed backend. Report loss on next write.
                with self.condition:
                    self.dropped += dropped + original_count
                    self.write_errors += errors + 1
            finally:
                with self.condition:
                    self.active = False
                    self.condition.notify_all()

    def flush(self, timeout=1.0):
        deadline = time.monotonic() + max(0, timeout)
        with self.condition:
            while self.pending or self.active:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.condition.wait(remaining)
            return True

    def close(self, timeout=1.0):
        with self.condition:
            self.stopping = True
            self.condition.notify_all()
        self.thread.join(max(0, timeout))
        return not self.thread.is_alive()
