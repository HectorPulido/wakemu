"""Operation-local transfer for the two native World cast producers.

Only Registry's private pair can enter. The World callsite owns its native LOS
and serializer callbacks; arbitrary transaction callers retain clone/rollback.
The lease expires before publication and cannot authorize a later transaction.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from .combat_owned_equipment_factory import OwnedEquipmentRuntimeFactory
from .combat_effect_runtime import NativeEffectRuntimeFactory

_FACTORY_CALL = NativeEffectRuntimeFactory.__call__
_OWNED_FACTORY_CALL = OwnedEquipmentRuntimeFactory.__call__

_PAIR = ContextVar("registry_private_spell_pair", default=None)
_ENTRY = ContextVar("world_owned_native_spell_entry", default=None)


@dataclass(eq=False)
class _Source:
    pair: object
    fight: object
    runtime: object
    action_id: int
    serializer: object
    consumed: bool = False


@contextmanager
def registry_private_spell_pair(fight, runtime):
    from .combat_state import Fight
    from .combat_runtime_messages import RuntimeMessages

    pair = (
        (fight, runtime)
        if (
            type(fight) is Fight
            and type(runtime) is RuntimeMessages
            and runtime.fight is fight
        )
        else None
    )
    token = _PAIR.set(pair)
    try:
        yield
    finally:
        _PAIR.reset(token)


@contextmanager
def owned_native_spell_entry(runtime, producer, *, stats_serializer, enabled=True):
    """Internal World scope: callbacks must be the unchanged native callsite."""
    from . import combat_server_spell as spell, combat_weapon as weapon
    from .combat_owned_spell_delivery import _METHODS
    from .combat_runtime_messages import RuntimeMessages

    pair = _PAIR.get()
    eligible = (
        enabled is True
        and pair is not None
        and pair[1] is runtime
        and runtime.fight is pair[0]
        and runtime.awaiting_ack is None
        and not runtime.pending
        and callable(stats_serializer)
        and all(
            name not in vars(runtime) and getattr(RuntimeMessages, name) is method
            for name, method in _METHODS.items()
        )
        and (
            (
                producer is spell._OWNED_PREPARE_SERVER_SPELL
                and spell.prepare_server_spell is producer
                and spell.server_runtime is spell._OWNED_SERVER_RUNTIME
            )
            or (
                producer is weapon._OWNED_PREPARE_SERVER_WEAPON
                and weapon.prepare_server_weapon is producer
                and spell.server_runtime is spell._OWNED_SERVER_RUNTIME
            )
        )
    )
    source = (
        _Source(pair, pair[0], runtime, runtime.action_id + 1, stats_serializer)
        if eligible
        else None
    )
    token = _ENTRY.set((source, producer) if source is not None else None)
    try:
        yield
    finally:
        # Transactions may escape for incident/reporting use. An expired
        # marker must not retain the private runtime or World closure graph.
        if source is not None:
            source.pair = source.fight = source.runtime = source.serializer = None
        _ENTRY.reset(token)


def owned_entry_preview(fight, *, producer, factory, action_id):
    from .combat_owned_equipment_factory import OwnedEquipmentRuntimeFactory
    from .combat_effect_runtime import NativeEffectRuntimeFactory

    current = _ENTRY.get()
    if current is None:
        return None
    source, expected = current
    if (
        expected is not producer
        or source.pair is not _PAIR.get()
        or source.fight is not fight
        or source.runtime.fight is not fight
        or source.action_id != action_id
        or source.consumed
        or type(factory) is not OwnedEquipmentRuntimeFactory
        or type(factory._factory) is not NativeEffectRuntimeFactory
        or OwnedEquipmentRuntimeFactory.__call__ is not _OWNED_FACTORY_CALL
        or NativeEffectRuntimeFactory.__call__ is not _FACTORY_CALL
        or "__call__" in vars(factory._factory)
    ):
        return None
    source.consumed = True
    return source, fight


def owns_entry_commit(runtime, transaction, serializer):
    current = _ENTRY.get()
    if current is None:
        return False
    source = current[0]
    return (
        type(transaction.source_state) is _Source
        and transaction.source_state is source
        and source.consumed
        and source.pair is _PAIR.get()
        and source.runtime is runtime
        and source.fight is runtime.fight
        and transaction.fight is source.fight
        and transaction.action_id == source.action_id
        and serializer is source.serializer
    )


def owns_private_pair(fight, runtime):
    """Identity-only issuer proof; consumers must separately certify their route."""
    pair = _PAIR.get()
    return (
        pair is not None
        and pair[0] is fight
        and pair[1] is runtime
        and runtime.fight is fight
    )
