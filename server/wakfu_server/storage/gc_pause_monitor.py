"""Bounded GC pause facts; profiler interaction stays outside GC callbacks."""
from collections import deque
import gc
import threading
import time


HISTORY_CAPACITY = 32


class GCPauseMonitor:
    def __init__(
        self,
        *,
        capacity=256,
        wall_clock=time.perf_counter,
        cpu_clock=time.thread_time,
        utc_clock=time.time,
        callbacks=None,
    ):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Invalid GC observation capacity")
        self.records = deque(maxlen=capacity)
        self.history = deque(maxlen=HISTORY_CAPACITY)
        self.longest = {}
        self.sequence = 0
        self.drained_sequence = 0
        self.starts = {}
        self.wall_clock = wall_clock
        self.cpu_clock = cpu_clock
        self.utc_clock = utc_clock
        self.callbacks = gc.callbacks if callbacks is None else callbacks
        self.callback = self._callback

    def install(self):
        if self.callback not in self.callbacks:
            self.callbacks.append(self.callback)
        return self

    def uninstall(self):
        if self.callback in self.callbacks:
            self.callbacks.remove(self.callback)
        self.starts.clear()

    def _callback(self, phase, info):
        # GC may run while the profiler owns its lock. Never observe, log, or
        # acquire a lock here; capture only small bounded timing records.
        try:
            generation = info.get("generation")
            if type(generation) is not int or generation not in (0, 1, 2):
                return
            key = (threading.get_ident(), generation)
            if phase == "start":
                if len(self.starts) >= 16:
                    self.starts.pop(next(iter(self.starts)))
                self.starts[key] = (
                    self.wall_clock(),
                    self.cpu_clock(),
                    self.utc_clock(),
                )
            elif phase == "stop":
                started = self.starts.pop(key, None)
                if started is not None:
                    self.sequence += 1
                    record = (
                        generation,
                        max(0.0, self.wall_clock() - started[0]),
                        max(0.0, self.cpu_clock() - started[1]),
                        self.sequence,
                        started[2],
                        self.utc_clock(),
                    )
                    self.records.append(record)
                    self.history.append(record)
                    previous = self.longest.get(generation)
                    if previous is None or record[1] > previous[1]:
                        self.longest[generation] = record
        except Exception:
            # Diagnostic faults must never affect collection or gameplay.
            return

    def drain(self, profiler):
        # Limit each drain even if another thread continuously collects.
        prior_sequence = self.drained_sequence
        observed = set()
        for _ in range(len(self.records)):
            try:
                generation, wall, cpu, sequence, _, _ = self.records.popleft()
            except IndexError:
                break
            if sequence <= prior_sequence:
                continue
            profiler.observe(f"diagnostics.gc.gen{generation}", wall, cpu)
            observed.add(sequence)
        # A long pause must survive subsequent short-collection churn even
        # when the bounded queue overflows before the writer gets CPU time.
        # Keep three scalar records; callbacks still never call the profiler.
        for generation in (0, 1, 2):
            record = self.longest.get(generation)
            if record is None:
                continue
            _, wall, cpu, sequence, _, _ = record
            if sequence > prior_sequence and sequence not in observed:
                profiler.observe(f"diagnostics.gc.gen{generation}", wall, cpu)
                observed.add(sequence)
        self.drained_sequence = max(prior_sequence, max(observed, default=0))

    def history_snapshot(self):
        """Return the bounded timestamped pause history as JSON-safe scalars."""
        records = self.history.copy()
        return [
            {
                "generation": generation,
                "started_at_utc_epoch_seconds": started_at,
                "ended_at_utc_epoch_seconds": ended_at,
                "duration_seconds": wall,
                "thread_cpu_seconds": cpu,
            }
            for generation, wall, cpu, _, started_at, ended_at in records
        ]


MONITOR = GCPauseMonitor()
