"""Coalesce static-source work by identity, without a global I/O gate.

Only immutable document/geometry producers belong here. Transaction contexts,
actors, RNGs and live occupancy must never be shared through this coordinator.
The caller's bounded cache remains responsible for completed-value retention.
"""
from concurrent.futures import Future
from threading import Lock, get_ident
import time


class NativeSourceFlights:
    def __init__(self, wait_label=None):
        self._lock = Lock()
        self._pending = {}
        self._leaders = 0
        self._shared_calls = 0
        self._wait_seconds = 0.0
        self._wait_label = wait_label

    def run(self, key, producer):
        if not callable(producer):
            raise TypeError("Native source producer must be callable")
        owner = get_ident()
        with self._lock:
            entry = self._pending.get(key)
            if entry is None:
                future = Future()
                self._pending[key] = (future, owner)
                self._leaders += 1
                leader = True
            else:
                future, source_owner = entry
                if source_owner == owner and not future.done():
                    raise RuntimeError("Recursive load of the same native source")
                self._shared_calls += 1
                leader = False
        if leader:
            try:
                value = producer()
            except BaseException as error:
                future.set_exception(error)
                raise
            else:
                future.set_result(value)
                return value
            finally:
                with self._lock:
                    if self._pending.get(key, (None,))[0] is future:
                        del self._pending[key]
        started = time.monotonic()
        try:
            return future.result()
        finally:
            elapsed = time.monotonic() - started
            with self._lock:
                self._wait_seconds += elapsed
            # Instrumentation must not extend a coordination lock or alter a
            # source-validation failure. Labels are fixed by the two callers.
            if self._wait_label is not None:
                try:
                    from .performance_profiler import PROFILER

                    PROFILER.observe(self._wait_label, elapsed)
                except Exception:
                    pass

    def statistics(self):
        with self._lock:
            return dict(
                leaders=self._leaders,
                shared_calls=self._shared_calls,
                active=len(self._pending),
                wait_seconds=self._wait_seconds,
            )
