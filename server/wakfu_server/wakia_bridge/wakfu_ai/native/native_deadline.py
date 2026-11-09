"""Cooperative owner-thread deadline shared by native SDK operations."""
from contextlib import contextmanager
from contextvars import ContextVar
import time
import math

try:
    from wakfu_server.combat_input_observation import observe_clock
except ModuleNotFoundError as error:
    # The standalone planner has no world engine on its import path. Only
    # that exact absence is optional; broken world dependencies must surface.
    if error.name != "wakfu_server":
        raise

    def observe_clock(label, value):
        return value


_ACTIVE = ContextVar("wakfu_native_ai_deadline", default=None)
_CLEANUP_ACTIVE = ContextVar("wakfu_native_ai_cleanup_active", default=False)


class NativeSearchAllowanceExceeded(TimeoutError):
    """A private query exhausted search time while its owner can still commit."""


def remaining():
    active = _ACTIVE.get()
    if active is None:
        return None
    deadline, clock = active
    value = deadline - observe_clock("native_deadline.monotonic", clock())
    if value <= 0:
        raise TimeoutError("Native AI turn deadline reached")
    return value


def check():
    remaining()


def clock_now():
    """Use the active owner's monotonic clock for elapsed RPC accounting."""
    active = _ACTIVE.get()
    return time.monotonic() if active is None else active[1]()


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


@contextmanager
def cleanup_budget(*, clock=time.monotonic):
    """Allow one cancellation attempt after expiry, capped at 250 ms.

    This scope is only for releasing remote search resources. It must never
    wrap native previews, commits or turn barriers. Restore the owner's exact
    prior deadline on every exit; nested cleanup cannot renew the allowance.
    """
    if _CLEANUP_ACTIVE.get():
        with bounded(clock() + 0.25, clock=clock):
            yield
        return
    token = _ACTIVE.set((clock() + 0.25, clock))
    cleanup_token = _CLEANUP_ACTIVE.set(True)
    try:
        check()
        yield
    finally:
        _CLEANUP_ACTIVE.reset(cleanup_token)
        _ACTIVE.reset(token)


@contextmanager
def query_budget(*, allowance_ms=None, reserve_ms=500):
    """Narrow a private query to search time, preserving the owner allowance.

    Checks remain cooperative. An opaque operation can return late, but that
    result is rejected; this scope does not claim to preempt arbitrary Python.
    Use the owner's clock, including deterministic clocks used by adapters.
    """
    if (
        type(reserve_ms) is not int
        or not 0 <= reserve_ms <= 10000
        or (
            allowance_ms is not None
            and (
                type(allowance_ms) not in (int, float)
                or not math.isfinite(allowance_ms)
                or allowance_ms < 0
            )
        )
    ):
        raise ValueError("Invalid native query search allowance")
    owner = _ACTIVE.get()
    available = remaining()
    if available is None and allowance_ms is None:
        yield
        return
    clock = owner[1] if owner is not None else time.monotonic
    allowance = None if allowance_ms is None else allowance_ms / 1000
    if available is not None:
        owner_search = max(0.0, available - reserve_ms / 1000)
        allowance = owner_search if allowance is None else min(allowance, owner_search)
    if allowance <= 0:
        raise NativeSearchAllowanceExceeded("Native query search allowance exhausted")
    deadline = clock() + allowance
    try:
        with bounded(deadline, clock=clock):
            yield
            check()
    except TimeoutError as error:
        # A real owner expiry is still fatal, as is an unrelated operation
        # timeout before this query's deadline. Only a search expiry is an
        # ordinary unsupported outcome that may retain an earlier incumbent.
        if clock() < deadline:
            raise
        if owner is not None and owner[0] - owner[1]() <= 0:
            raise
        raise NativeSearchAllowanceExceeded(
            "Native query search allowance exhausted"
        ) from error
