"""Cooperative owner-thread deadline shared by native SDK operations."""
from contextlib import contextmanager
from contextvars import ContextVar
import time

_ACTIVE = ContextVar("wakfu_native_ai_deadline", default=None)


def remaining():
    active = _ACTIVE.get()
    if active is None:
        return None
    deadline, clock = active
    value = deadline - clock()
    if value <= 0:
        raise TimeoutError("Native AI turn deadline reached")
    return value


def check():
    remaining()


@contextmanager
def bounded(deadline, *, clock=time.monotonic):
    previous = _ACTIVE.get()
    if previous is not None:
        # Nested operations may narrow a deadline, never grant more time.
        available = remaining()
        deadline = min(deadline, clock() + available)
    token = _ACTIVE.set((deadline, clock))
    try:
        check()
        yield
    finally:
        _ACTIVE.reset(token)
