"""Pre-pin proof sketch for native retained healing lifecycle capability.

This prototype is intentionally outside the server package. It never invokes a
callback or constructs a dispatcher before pinning. The preflight proves that
the production factory is statically wired to construct the ordinary healing
lifecycle for a type-12 item container. A separate post-construction check
attests that the expected retained wrappers actually exist before any owned
source is applied.
"""
from collections.abc import Mapping


def _native_factory(factory):
    from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
    from wakfu_server.combat_owned_equipment_factory import (
        OwnedEquipmentRuntimeFactory,
    )

    if type(factory) is OwnedEquipmentRuntimeFactory:
        factory = factory._factory
    if type(factory) is not NativeEffectRuntimeFactory:
        return None
    return factory


def preflight(factory, retained_container):
    """Return True only when production construction guarantees healing events.

    ``retained_container`` is the unmodified source plan returned by the native
    copied-equipment planner. Type/level checks intentionally describe the
    generic fnR/eHi container contract, not an item reference or topology.
    """
    from wakfu_server.combat_runtime_adapter import NativeRuntimeContexts
    from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
    from wakfu_server.combat_summon import ordinary_roster_authority

    runtime = _native_factory(factory)
    if runtime is None or not isinstance(retained_container, Mapping):
        return False
    if (
        retained_container.get("present") is not True
        or retained_container.get("type") != 12
        or retained_container.get("native_kind") != "item"
        or retained_container.get("is_spell") is not False
        or type(retained_container.get("id")) is not int
        or retained_container["id"] <= 0
        or type(retained_container.get("level")) is not int
        or not 0 <= retained_container["level"] <= 32767
    ):
        return False
    contexts = runtime.contexts
    if type(contexts) is not NativeRuntimeContexts:
        return False
    callback = contexts.healing_events
    adapter = getattr(callback, "__self__", None)
    if (
        not isinstance(adapter, NativeServerRuntimeAdapter)
        or getattr(callback, "__func__", None)
        is not NativeServerRuntimeAdapter.healing_events
        or adapter.actor_authority is not runtime.summon_authority
        or not ordinary_roster_authority(runtime.summon_authority)
    ):
        return False
    if not isinstance(runtime.state_catalog, Mapping):
        return False
    if not isinstance(runtime.state_catalog.get("states"), Mapping):
        return False
    if not isinstance(runtime.state_catalog.get("effects"), Mapping):
        return False
    # The exact factory class creates NativeRetainedRuntime and NativeEventReplay
    # from the plan container before it calls this typed callback. The callback
    # body returns None only if the same ordinary-roster condition fails.
    return True


def verify_initialized(dispatcher, preview, plan):
    """Verify the actual transaction-local objects before source application."""
    from wakfu_server.combat_dispel import NativeDispelHandler
    from wakfu_server.combat_effect_dispatch import EffectDispatcher
    from wakfu_server.combat_event_replay import NativeCloneAuthority
    from wakfu_server.combat_event_replay import NativeEventReplay
    from wakfu_server.combat_healing_handler import NativeHealingHandler
    from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents
    from wakfu_server.combat_retained_runtime import NativeRetainedRuntime

    if type(dispatcher) is not EffectDispatcher:
        return False
    retention = getattr(dispatcher, "native_retention", None)
    replay = getattr(dispatcher, "replay_event", None)
    if (
        type(retention) is not NativeRetainedRuntime
        or type(replay) is not NativeEventReplay
    ):
        return False
    if replay.dispatcher is not dispatcher or replay.retention is not retention:
        return False
    if retention.fight is not preview or retention.plan is not plan:
        return False
    handlers = getattr(dispatcher, "handlers", None)
    if not isinstance(handlers, Mapping):
        return False
    wrapped = handlers.get(25)
    raw = getattr(wrapped, "native_wrapped_handler", None)
    if (
        raw is None
        or type(raw) is not NativeHealingHandler
        or getattr(wrapped, "native_retention_owner", None) is not retention
        or raw.retention is not retention
    ):
        return False
    lifecycle = raw.event_lifecycle
    if (
        type(lifecycle) is not OrdinaryHealingEvents
        or lifecycle.preview is not preview
        or lifecycle.plan is not plan
        or lifecycle.replay is not replay
        or lifecycle.retention is not retention
        or not isinstance(lifecycle.authority, NativeCloneAuthority)
    ):
        return False
    dispel_wrapper = handlers.get(421)
    dispel = getattr(dispel_wrapper, "native_wrapped_handler", None)
    if (
        type(dispel) is not NativeDispelHandler
        or getattr(dispel_wrapper, "native_retention_owner", None) is not retention
    ):
        return False
    bindings = getattr(dispatcher, "operation_contracts", None)
    binding = bindings.get(25) if isinstance(bindings, Mapping) else None
    if binding is None or binding.handler is not wrapped:
        return False
    return True
