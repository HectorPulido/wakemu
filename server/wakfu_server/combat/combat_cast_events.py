"""Wakemu external cast boundaries, using native null-source Qf selection.

eFK identifies 1024/1025 as external events. Installed subscriptions inspect
the active spell and apply class states. Their original server producer is not
available: before-roots 1024 and successful-after-roots 1025 are explicit
Wakemu policy, not claims about an original client/server callsite.
"""
from contextlib import contextmanager
from .combat_active_spell import active_spell_container
from .combat_event_replay import NativeExternalEvent


POLICY = "wakemu.external-cast-boundaries-v1"


def validate_cast_boundary_context(context):
    if (
        not isinstance(context, dict)
        or context.get("policy") != POLICY
        or type(context.get("caster_id")) is not int
        or type(context.get("distance")) is not int
        or type(context.get("spell_id")) is not int
    ):
        raise ValueError("Invalid validated server cast boundary facts")
    return context


def cast_boundary_context(fight, plan):
    # Legacy focused dispatchers without a validated target have no policy
    # facts. Production plans contain the actual casting decision's target.
    if "target" not in plan:
        return None
    from .combat_condition_distance import DistanceActor, native_caster_target_distance

    caster = fight.actors[plan["actor_id"]]
    target = fight.actors.get(plan.get("target_id"))
    cell = plan["target"]
    if (
        not isinstance(cell, (tuple, list))
        or len(cell) != 3
        or any(type(v) is not int for v in cell)
    ):
        raise ValueError("Cast boundary requires validated target XYZ")
    distance = native_caster_target_distance(
        DistanceActor(*caster.position[:2], caster.physical_radius),
        DistanceActor(*target.position[:2], target.physical_radius)
        if target is not None
        else tuple(cell),
    )
    return validate_cast_boundary_context(
        dict(
            policy=POLICY,
            caster_id=caster.id,
            spell_id=plan["spell_id"],
            distance=distance,
        )
    )


def _deliver(dispatcher, plan, event_id, context=None, *, removal=False):
    fight = dispatcher.native_retention.fight
    authority = dispatcher.native_clone_authority
    caster_id = plan["actor_id"]
    outcomes = []
    # Native Qf mask2 is removal, selected only by4/40/41. External cast
    # activation6/60/61 cannot expire a one-cast listener. Deliver removal
    # after successful1025 reactions as an explicit Wakemu server policy.
    if removal and event_id != 1025:
        raise ValueError("Cast removal boundary requires successful1025")
    global_channel = 41 if removal else 61
    for channel in (4, 40) if removal else (6, 60):
        outcomes.extend(
            dispatcher.replay_event(
                NativeExternalEvent(
                    caster_id, (event_id,), channel, cast_boundary_context=context
                ),
                authority=authority,
            )
        )
    if hasattr(fight, "native_global_pv_collections"):
        from .combat_global_pv_collections import global_pv_iterator
        from .combat_state_managers import registered_area_pv

        for identity in global_pv_iterator(fight, caster_id=caster_id):
            if identity not in fight.actors:
                manager = registered_area_pv(fight, identity)
                if manager is None:
                    raise ValueError("Cast event global PV manager absent")
                if not manager.native_running_effect_manager:
                    continue
            outcomes.extend(
                dispatcher.replay_event(
                    NativeExternalEvent(
                        identity,
                        (event_id,),
                        global_channel,
                        cast_boundary_context=context,
                    ),
                    authority=authority,
                )
            )
    else:
        # Bare focused runtimes can have no global observers. Never invent
        # native map order from a Python roster when an observer does exist.
        from .combat_native_events import subscription_selection

        retention = dispatcher.native_retention
        for entry in retention.view().entries:
            row = fight.native_owned_group_effects.get(entry.uid)
            if row is None:
                continue
            definition = retention.metadata["effects"][str(entry.generic_effect)]
            if (
                subscription_selection(
                    masks=row["native_subscription_masks"],
                    event_ids=(event_id,),
                    channel=global_channel,
                    global_subscription=definition["event_global_subscription"],
                    reversed_subscription=definition["event_reverse_subscription"],
                    flags=row["native_effect_flags"],
                    source_present=False,
                )
                is not None
            ):
                raise ValueError(
                    "Global cast observer requires native PV collection producer"
                )
    return tuple(outcomes)


@contextmanager
def cast_event_scope(dispatcher, plan, *, origin="normal"):
    """Deliver one complete validated cast inside its unpublished transaction.

    Caller owns active PZ, cost policy and rollback. Nested effect-426 casts
    enter separately with their own active spell; effect-child groups do not.
    Restored running effects and replayed listeners are not new spell casts.
    """
    if origin not in ("normal", "nested"):
        raise ValueError("Unknown server cast event origin")
    if not hasattr(dispatcher, "native_retention"):
        # A custom non-native dispatcher has no retained Qf event subsystem.
        yield
        return
    fight = dispatcher.native_retention.fight
    caster_id = plan.get("actor_id")
    container = active_spell_container(fight)
    if (
        type(caster_id) is not int
        or caster_id not in fight.actors
        or container
        != dict(
            present=True,
            is_spell=True,
            spell_id=plan.get("spell_id"),
            level=plan.get("evaluation_level"),
        )
        or not callable(getattr(dispatcher, "replay_event", None))
        or not hasattr(dispatcher, "native_clone_authority")
    ):
        raise ValueError("Cast boundary requires owned active spell and runtime")
    context = cast_boundary_context(fight, plan)
    from .combat_attack_preparation import (
        attack_preparation_scope,
        settle_attack_preparation,
    )

    with attack_preparation_scope(fight, caster_id):
        _deliver(dispatcher, plan, 1024, context)
        yield
        # An exception in any root exits before the successful-after boundary.
        settle_attack_preparation(dispatcher)
        _deliver(dispatcher, plan, 1025, context)
        _deliver(dispatcher, plan, 1025, context, removal=True)
