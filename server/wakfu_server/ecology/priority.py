"""Admission priority for player requests over durable ecology work.

The worker retains deferred proposals in PostgreSQL. This module does not
acknowledge work or move live-world mutations to another thread.
"""
from contextlib import contextmanager
import threading


def is_interactive(proposal):
    return proposal["domain"] == "plants" and proposal["payload"].get("kind") in (
        "planting_begin",
        "planting_rejected",
    )


class InteractivePriority:
    def __init__(self):
        self._lock = threading.Lock()
        self._active = 0

    @contextmanager
    def interactive(self):
        with self._lock:
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1

    @property
    def interactive_active(self):
        with self._lock:
            return self._active > 0
