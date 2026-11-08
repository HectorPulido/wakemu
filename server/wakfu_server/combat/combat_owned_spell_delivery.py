"""Explicit transfer of a caller-owned cast pair after source validation."""
from contextlib import contextmanager
from contextvars import ContextVar
from .combat_runtime_messages import RuntimeMessages
from .combat_spell_transaction import SpellTransaction
from .combat_state import Fight


_CURRENT = ContextVar("native_owned_spell_delivery", default=None)
_METHODS = {
    name: getattr(RuntimeMessages, name)
    for name in (
        "prepare_fight_delivery",
        "prepare_delivery",
        "_flush",
        "_record_prepared_revivals",
    )
}


@contextmanager
def owned_spell_delivery(runtime, transaction, *, enabled=True):
    """Caller discards BOTH private inputs after any exception, without retry."""
    eligible = (
        enabled is True
        and type(runtime) is RuntimeMessages
        and type(transaction) is SpellTransaction
        and type(runtime.fight) is Fight
        and type(transaction.fight) is Fight
        and all(
            name not in vars(runtime) and getattr(RuntimeMessages, name) is method
            for name, method in _METHODS.items()
        )
    )
    token = _CURRENT.set((runtime, transaction, False) if eligible else None)
    try:
        yield
    finally:
        _CURRENT.reset(token)


@contextmanager
def validated_spell_delivery(runtime, transaction):
    """Called only after packet, serialization and second source checks."""
    current = _CURRENT.get()
    eligible = (
        current is not None
        and current[0] is runtime
        and current[1] is transaction
        and current[2] is False
        and all(
            name not in vars(runtime) and getattr(RuntimeMessages, name) is method
            for name, method in _METHODS.items()
        )
    )
    token = _CURRENT.set((runtime, transaction, True) if eligible else None)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def owns_spell_delivery(runtime, fight, action_id, operation):
    current = _CURRENT.get()
    return (
        current is not None
        and current[2] is True
        and current[0] is runtime
        and current[1].fight is fight
        and current[1].action_id == action_id
        and operation == "commit_spell_transaction"
    )
