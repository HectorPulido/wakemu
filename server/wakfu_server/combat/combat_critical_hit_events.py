"""Explicit Wakemu1016 policy: one event per completed critical damage hit.

Installed311728 describes a bonus for each critical hit inflicted. The original
server publisher is unavailable. The unit is one actual eXt runner/recipient
application after L4, including blocked/zero outcomes. There is no cast-level
counter, healing trigger, extra critical roll or replacement damage Qe.
"""
from collections.abc import Mapping


POLICY = "wakemu.completed-critical-damage-hit-v1"


def preflight(factory, retained_container, *, routes):
    """Attest the installed ordinary damage/retention construction only."""
    from .combat_equipment_event_scope import damage_events
    from .combat_equipment_retained_lifecycle import preflight as retained_preflight

    return retained_preflight(factory, retained_container) and 2 in damage_events(
        factory, routes
    )


def deliver_completed_critical_hit(
    handler, effect, invocation, *, uid, context, result
):
    """Called once by the damage consumer after actual application and L4.

    The handler supplies its actual validated execution context and consumption
    receipt. Publication stays inside its unpublished reversible transaction.
    Existing Qf routing and retained clone ownership are reused unchanged.
    """
    if context is None or context.critical is not True:
        return ()
    from .combat_damage_handler import DamageExecutionContext, NativeDamageHandler
    from .combat_ordinary_events import OrdinaryDamageEvents

    if not isinstance(context, DamageExecutionContext) or not isinstance(
        handler, NativeDamageHandler
    ):
        raise ValueError("Critical hit requires actual native damage execution")
    lifecycle = handler.event_lifecycle
    if lifecycle is None:
        return ()  # Focused consumers without ordinary retained event machinery.
    if type(lifecycle) is not OrdinaryDamageEvents:
        return ()
    from .combat_event_replay import NativeEventReplay
    from .combat_retained_runtime import NativeRetainedRuntime

    replay = lifecycle.replay
    retention = lifecycle.retention
    if (
        type(replay) is not NativeEventReplay
        or type(retention) is not NativeRetainedRuntime
        or replay.retention is not retention
        or replay.dispatcher.native_retention is not retention
        or lifecycle.preview is not handler.fight
        or retention.fight is not handler.fight
        or handler.retention is not retention
        or lifecycle.plan is not retention.plan
        or type(uid) is not int
        or uid <= 0
        or not isinstance(result, Mapping)
        or type(result.get("value")) is not int
        or type(effect.get("effect_class")) is not int
    ):
        raise ValueError("Critical hit lost its actual damage/replay authority")
    # No listener means no extra Qf iteration/global-recipient lookup. Native
    # state admission/timers still own whether a1016 listener is retained.
    groups = getattr(handler.fight, "native_owned_group_effects", {})
    if not any(
        isinstance(row, Mapping)
        and isinstance(row.get("native_subscription_masks"), (list, tuple))
        and len(row["native_subscription_masks"]) == 7
        and 1016 in (row["native_subscription_masks"][5] or ())
        for row in groups.values()
    ):
        return ()
    # This external owner notification addresses an ordinary fighter's Qf.
    # Detached constructor sources and casters already retired by L4 do not
    # acquire a replacement player/master manager. Their existing damage
    # application remains valid; they have no registered owner Qf to notify.
    if invocation.caster_id not in handler.fight.actors:
        return ()
    from .combat_cast_events import _deliver

    # 1016 is an external event, like the installed1024/1025 policy. Reuse its
    # exact local/reversed/global Qf delivery, without manufacturing a Qe or
    # borrowing this damage runner's mutable amount as a trigger context.
    return _deliver(replay.dispatcher, {"actor_id": invocation.caster_id}, 1016)
