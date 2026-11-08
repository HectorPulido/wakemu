"""Private ownership token for a native shared-turn transaction."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


_WORLD_NATIVE_RUNNER = object()
_CURRENT = ContextVar("wakfu_shared_native_commit", default=None)


@dataclass(frozen=True)
class _Ownership:
    runtime: object
    claim: tuple
    sequence: int


@contextmanager
def shared_native_turn(runtime, claim, sequence, *, issuer):
    """Authorize only the exact private runtime issued by World shared-turn."""
    if (
        issuer is not _WORLD_NATIVE_RUNNER
        or type(claim) is not tuple
        or len(claim) != 3
        or type(sequence) is not int
        or sequence < 0
    ):
        yield False
        return
    ownership = _Ownership(runtime, claim, sequence)
    token = _CURRENT.set(ownership)
    try:
        yield True
    finally:
        _CURRENT.reset(token)


def owns_shared_native_action(runtime, action_type):
    """Return the same owner proof for a supported native action branch."""
    ownership = _CURRENT.get()
    return (
        type(action_type) is str
        and action_type in {"end_turn", "cast"}
        and type(ownership) is _Ownership
        and ownership.runtime is runtime
        and type(ownership.claim) is tuple
        and len(ownership.claim) == 3
        and type(ownership.sequence) is int
        and ownership.sequence >= 0
    )
