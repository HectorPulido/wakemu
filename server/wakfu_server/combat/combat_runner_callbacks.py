"""Ephemeral native eVt/eYz observer identity; no UID or wire value inference."""
from contextlib import contextmanager
from contextvars import ContextVar

_active = ContextVar("native_runner_value_observers", default=())


class _RunnerValueObserver:
    def __init__(self, callback):
        self.callback = callback
        self.consumed = False


@contextmanager
def runner_value_scope(callback):
    """Yield identity attached only to invocations sharing the observed eVt.

    A new eVt builder must clear this identity, even with identical wire bytes.
    eYz.h removes itself after its first callback, including when value is zero.
    """
    if not callable(callback):
        raise ValueError("Native runner value callback required")
    observer = _RunnerValueObserver(callback)
    token = _active.set((*_active.get(), observer))
    try:
        yield observer
    finally:
        _active.reset(token)


def notify_runner_value(invocation, value):
    """Call after Qe.bbK's lifecycle phases, with the runner's final aSg."""
    observer = getattr(invocation, "native_value_scope", None)
    if observer is None:
        return
    if not isinstance(observer, _RunnerValueObserver) or observer not in _active.get():
        raise ValueError("Native runner observer escaped its synchronous context")
    if observer.consumed:
        return
    if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
        raise ValueError("Actual native signed runner value required")
    observer.consumed = True  # eYz.h removes itself even on zero.
    observer.callback(invocation, value)
