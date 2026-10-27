"""Explicit Wakemu notifications for actual range/willpower maximum changes.

The ffw identifiers are original. Their installed producers were not recovered:
eWN/eWO do not bind these PCs in eVi, and eWU never registers these identifiers.
The post-mutation policy observes a completed existing eWU setter (or its owned
inverse). A separately declared PC86 L2 intention precedes application, like the
original eWN/eWO constructor bit; its callbacks/clamps may leave no actual delta.
Current-value writes never enter either policy.
"""

from copy import deepcopy
import json


POLICY = "wakemu.actual-parameter-maximum-events.v1"
INTENT_POLICY = "wakemu.parameter-maximum-L2-intent.v1"
MAXIMUM_EVENTS = {11: (None, 208), 86: (2257, 2258)}
_SOURCE_FIELDS = (
    "effect_class",
    "variant",
    "minimum_level",
    "maximum_level",
    "parameters",
    "native_execution_mode",
    "native_effect_flags",
    "target_masks",
)


def maximum_event_ids(stat, before, after):
    """Classify effective PA maxima, after all existing clamps and arithmetic."""
    if type(stat) is not int or any(
        type(value) is not int or not -(1 << 31) <= value < (1 << 31)
        for value in (before, after)
    ):
        raise ValueError("Missing actual native maximum setter images")
    if stat not in MAXIMUM_EVENTS or before == after:
        return ()
    event = MAXIMUM_EVENTS[stat][0 if after > before else 1]
    return () if event is None else (event,)


def notify_intent(lifecycle, fight, actor, stat, *, effect, invocation, uid, value):
    """PC86's real eWU operation intends gain/loss before its setter executes.

    As with eWN/eWO constructor identifiers, direction belongs to the operation
    family, not a prediction of effective PA delta. The original running amount
    may be zero or signed; no RNG, provisional setter or second UID is used.
    """
    if lifecycle is None or stat != 86:
        return False
    family = effect.get("effect_class")
    if (
        family not in (1201, 1202)
        or lifecycle.preview is not fight
        or fight.actors.get(actor.id) is not actor
        or invocation.target_id != actor.id
        or invocation.caster_id not in fight.actors
        or not isinstance(actor.effect_maxima, dict)
        or type(actor.effect_maxima.get(stat)) is not int
        or type(value) is not int
        or not -(1 << 31) <= value < (1 << 31)
    ):
        raise ValueError("Maximum intention requires its actual native setter source")
    with lifecycle.retention.container_scope(invocation):
        lifecycle.phase(
            effect,
            invocation,
            uid=uid,
            value=value,
            channel=2,
            _event_ids=(2257 if family == 1201 else 2258,),
        )
    return True


def capture_source(lifecycle, effect, invocation, uid):
    """Save bounded plain original source facts for the owned inverse setter."""
    if lifecycle is None:
        return None
    retention = lifecycle.retention
    retention.definition(effect, invocation)
    container, identity = retention.container(invocation)
    direct = None
    if invocation.state_uid is None:
        direct = invocation.native_retained_container
        if direct is None:
            direct = retention.plan.get("native_retained_container")
        if direct is None:
            present, level = retention.container_level(invocation)
            direct = {"present": present}
            if present:
                direct.update(
                    type=container["container_type"],
                    id=identity,
                    is_spell=container["container_is_spell"],
                    level=level,
                    native_kind=container.get("container_kind"),
                )
                if direct["is_spell"]:
                    direct.update(
                        protected=container["spell_protected"],
                        spell_id=retention.plan["spell_id"],
                    )
    source = dict(
        policy=POLICY,
        effect={key: deepcopy(effect[key]) for key in _SOURCE_FIELDS},
        invocation=dict(
            reference=invocation.reference,
            level=invocation.level,
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            cell=list(invocation.cell),
            base_uid=invocation.base_uid,
            state_uid=invocation.state_uid,
            native_running_uid=uid,
            native_context_hex=invocation.native_context_hex,
            native_trigger_context=deepcopy(invocation.native_trigger_context),
            native_retained_container=deepcopy(direct),
        ),
    )
    # Do not persist ephemeral callbacks, scoped observers or an unbounded graph.
    encoded = json.dumps(source, allow_nan=False, separators=(",", ":"))
    if len(encoded.encode()) > 16384:
        raise ValueError("Maximum-change source exceeds its bounded plain contract")
    return json.loads(encoded)


def inverse_source(handler, entry):
    """Validate the original registered source before an inverse mutates PA."""
    saved = entry.get("maximum_event_source")
    if saved is None:
        return None  # Older native entries predate this explicit server policy.
    from .combat_effect_dispatch import EffectInvocation
    from .combat_effect_removal import _identity_fields

    lifecycle = getattr(handler, "event_lifecycle", None)
    if (
        lifecycle is None
        or not isinstance(saved, dict)
        or saved.get("policy") != POLICY
        or not isinstance(saved.get("effect"), dict)
        or not isinstance(saved.get("invocation"), dict)
    ):
        raise ValueError("Missing retained maximum-change source authority")
    effect = saved["effect"]
    invocation = EffectInvocation(
        **dict(saved["invocation"], cell=tuple(saved["invocation"]["cell"]))
    )
    fields = _identity_fields(bytes.fromhex(entry["payload"]))
    record = handler.fight.native_retained_records.get(entry["uid"])
    if (
        effect.get("effect_class") != entry["effect_class"]
        or effect.get("effect_class") not in (1201, 1202)
        or invocation.native_running_uid != entry["uid"]
        or invocation.caster_id != entry["caster_id"]
        or invocation.target_id != entry["target_id"]
        or fields.get(1) != entry["uid"]
        or fields.get(3) != invocation.reference
        or fields.get(6) != invocation.caster_id & ((1 << 64) - 1)
        or invocation.target_id is None
        or fields.get(7) != invocation.target_id & ((1 << 64) - 1)
        or record is None
        or record.get("generic_effect") != invocation.reference
        or record.get("effect_class") != entry["effect_class"]
        or record.get("target_id") != entry["target_id"]
    ):
        raise ValueError("Retained maximum source differs from its original Qe")
    lifecycle.retention.definition(effect, invocation)
    actual, identity = lifecycle.retention.container(invocation)
    if actual["container_present"] and identity != record.get("container_id"):
        raise ValueError("Retained maximum source container identity changed")
    for field in ("container_present", "container_type", "container_is_spell"):
        if actual.get(field) != record.get(field):
            raise ValueError("Retained maximum source container changed")
    return effect, invocation


def notify(lifecycle, fight, actor, stat, before, *, effect, invocation, uid, value):
    """Replay after a completed real setter, with the unchanged original Qe."""
    if lifecycle is None:
        return False
    if (
        lifecycle.preview is not fight
        or fight.actors.get(actor.id) is not actor
        or invocation.target_id != actor.id
        or invocation.caster_id not in fight.actors
        or not isinstance(actor.effect_maxima, dict)
        or stat not in actor.effect_maxima
    ):
        raise ValueError("Maximum event requires the actual registered setter PA")
    events = maximum_event_ids(stat, before, actor.effect_maxima[stat])
    if not events:
        return False
    # Preserve the actual PL while L3 reactions can remove its state owner.
    with lifecycle.retention.container_scope(invocation):
        for channel in (3, 4):
            lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=value,
                channel=channel,
                _event_ids=events,
            )
    return True


def available_maximum_characteristic_events(factory, routes, *, phase):
    """Prove the existing parameter setter's exact production construction.

    eWU is not an equipment operation route. The exact factory class constructs
    it unconditionally; typed ordinary retention/stat callbacks establish its
    event lifecycle. Do not fabricate an equipment binding for that constructor.
    """
    if type(phase) is not int or phase not in (2, 3, 4):
        return frozenset()
    from .combat_equipment_operation_capability import FactoryOperationRoutes
    from .combat_equipment_retained_lifecycle import _native_factory
    from .combat_runtime_adapter import (
        NativeRuntimeContexts,
        NativeServerRuntimeAdapter,
    )
    from .combat_summon import ordinary_roster_authority

    runtime = _native_factory(factory)
    if (
        type(routes) is not FactoryOperationRoutes
        or routes.factory is not runtime
        or runtime is None
    ):
        return frozenset()
    callback = runtime.contexts.healing_events
    adapter = getattr(callback, "__self__", None)
    if (
        type(runtime.contexts) is not NativeRuntimeContexts
        or not isinstance(adapter, NativeServerRuntimeAdapter)
        or getattr(callback, "__func__", None)
        is not NativeServerRuntimeAdapter.healing_events
        or adapter.actor_authority is not runtime.summon_authority
        or not ordinary_roster_authority(runtime.summon_authority)
        or not callable(runtime.contexts.stat)
        or runtime.contexts.stat
        is not getattr(getattr(adapter, "cast", None), "stat", None)
    ):
        return frozenset()
    return frozenset((2257, 2258) if phase == 2 else (208, 2257, 2258))
