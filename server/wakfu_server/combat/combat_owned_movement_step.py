"""Private movement child ownership, scoped beneath Registry rollback.

World attests its unchanged native provider. The outer movement preview and its
baseline remain distinct; only consumed step payments may reuse that preview.
"""
from contextlib import contextmanager
from contextvars import ContextVar

_ENTRY = ContextVar("owned_native_movement_entry", default=None)
_CHILD = ContextVar("owned_native_movement_child", default=None)
_STEP = ContextVar("owned_native_movement_step", default=None)


def _native_route():
    from . import combat_area_transaction as area, combat_server_spell as spell
    from . import combat_movement_runtime as movement

    return (
        area.prepare_area_movement is area._OWNED_PREPARE_AREA_MOVEMENT
        and spell.server_runtime is spell._OWNED_SERVER_RUNTIME
        and movement.apply_client is movement._OWNED_APPLY_CLIENT
    )


@contextmanager
def owned_native_movement(runtime, provider, *, enabled=True):
    """Internal World scope, entered only for its certified native closure."""
    from .combat_owned_native_spell_entry import owns_private_pair

    entry = (
        (runtime, provider)
        if enabled is True
        and provider is not None
        and owns_private_pair(runtime.fight, runtime)
        and _native_route()
        else None
    )
    token = _ENTRY.set(entry)
    try:
        yield
    finally:
        _ENTRY.reset(token)


@contextmanager
def movement_child_preview(runtime, candidate, provider):
    from .combat_owned_native_spell_entry import owns_private_pair
    from .combat_runtime_messages import RuntimeMessages
    from .combat_state import Fight

    entry = _ENTRY.get()
    valid = (
        entry is not None
        and entry[0] is runtime
        and entry[1] is provider
        and owns_private_pair(runtime.fight, runtime)
        and _native_route()
        and type(candidate) is RuntimeMessages
        and type(candidate.fight) is Fight
        and candidate is not runtime
        and candidate.fight is not runtime.fight
    )
    token = _CHILD.set((candidate.fight, entry) if valid else None)
    try:
        yield
    finally:
        _CHILD.reset(token)


@contextmanager
def owned_step_preview(fight, payment):
    from .combat_movement_payment_events import WakemuMovementPolicy

    child = _CHILD.get()
    valid = (
        child is not None
        and child[0] is fight
        and child[1] is _ENTRY.get()
        and _native_route()
        and type(payment) is WakemuMovementPolicy
        and payment.source_fight is fight
        and not payment.publication
    )
    token = _STEP.set((fight, payment, child) if valid else None)
    try:
        yield valid
    finally:
        _STEP.reset(token)


def owns_step_preview(fight, payment):
    step = _STEP.get()
    return (
        step is not None
        and step[0] is fight
        and step[1] is payment
        and step[2] is _CHILD.get()
        and step[2][1] is _ENTRY.get()
    )
