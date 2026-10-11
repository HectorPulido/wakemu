"""Common spell request -> ordered effects, with a single commit boundary.

Runtime factory must bind all handlers, queues and characteristic mutations to
preview only. No network emission is permitted before this function returns.
An eligible effect without a handler rejects the entire cast, including costs.
"""
from copy import deepcopy
from dataclasses import dataclass
from .combat_cast import prepare_spell_cast
from .combat_effect_dispatch import EffectDispatcher, EffectInvocation
from .combat_spells import cast_animation, cast_notification
from .combat_geometry_snapshot import source_snapshot
from .combat_active_spell import active_spell_scope
from .combat_cast_facing import mirror_cast_facing
from .combat_transaction_rng import transactional_spell_rng
from .combat_cast_events import cast_event_scope


@dataclass(frozen=True)
class SpellTransaction:
    fight: object
    plan: dict
    wp_remaining: int
    outcomes: tuple
    packets: tuple
    events: tuple
    source_state: dict
    action_id: int


@transactional_spell_rng
def prepare_spell_transaction(
    body,
    character,
    fight,
    owner_id,
    deck_blob,
    *,
    wp_current,
    action_id,
    line_of_sight,
    runtime_factory,
    conditional_context=None,
    critical=False
):
    """Validate and execute every native root on one authoritative preview.

    Factory(preview, plan) returns (dispatcher, packet_list). The list contains
    owned (opcode, payload) pairs and stays private until successful completion.
    Returning a transaction does not commit it to a session or send packets.
    """
    if type(wp_current) is not int or wp_current < 0:
        raise ValueError("Invalid authoritative WP")
    if type(action_id) is not int or not 0 < action_id < 1 << 31:
        raise ValueError("Invalid spell action ID")
    if type(critical) is not bool:
        raise ValueError("Missing explicit critical branch")
    source_state = source_snapshot(fight)
    preview = deepcopy(fight)
    plan = prepare_spell_cast(
        body,
        character,
        preview,
        owner_id,
        deck_blob,
        wp=wp_current,
        line_of_sight=line_of_sight,
        conditional_context=conditional_context,
    )
    event_start = len(preview.events)
    caster = preview.actors[plan["actor_id"]]
    from .combat_normal_execution_origin import (
        normal_execution_origin,
        normal_root_context,
    )

    wp_remaining = wp_current - plan["costs"]["wp"]
    if caster.effect_stats is not None and 4 in caster.effect_stats:
        if caster.effect_stats[4] != wp_current:
            raise ValueError("WP snapshot disagrees with authoritative resource")
        caster.effect_stats[4] = wp_remaining
    from .combat_resource_pa_notifications import notify_resource_pa

    if getattr(caster, "effect_resource_raw_currents", None) is not None:
        from .combat_resource_pa_notifications import shift_resource_current

        shift_resource_current(preview, caster, 2, plan["costs"]["ap"], subtract=True)
        shift_resource_current(preview, caster, 3, plan["costs"]["mp"], subtract=True)
    else:
        before_ap = caster.ap
        caster.ap -= plan["costs"]["ap"]
        if caster.effect_stats is not None and 2 in caster.effect_stats:
            caster.effect_stats[2] = caster.ap
        notify_resource_pa(preview, caster, 2, before_current=before_ap)
        caster.mp -= plan["costs"]["mp"]
        if caster.effect_stats is not None and 3 in caster.effect_stats:
            caster.effect_stats[3] = caster.mp
    from .combat_spell_resource_costs import pay_extra_resources

    plan["extra_resource_payment"] = pay_extra_resources(
        caster, plan["costs"]["extra_resource_deltas"], fight=preview
    )
    mirror_cast_facing(caster, plan, fight=preview)
    dispatcher, effect_packets = runtime_factory(preview, plan)
    if not isinstance(dispatcher, EffectDispatcher) or not isinstance(
        effect_packets, list
    ):
        raise ValueError(
            "Runtime factory must return dispatcher and private packet list"
        )
    execution_origin = normal_execution_origin(plan)
    with active_spell_scope(
        preview, plan["spell_id"], level=plan["evaluation_level"]
    ), preview.effect_resolution(), cast_event_scope(dispatcher, plan):
        from .combat_cost_payment_events import replay_paid_spell_costs

        replay_paid_spell_costs(dispatcher, plan)
        from .combat_breeze_payment_events import replay_paid_breeze_costs

        replay_paid_breeze_costs(dispatcher, plan)
        outcomes = tuple(
            dispatcher.execute(
                EffectInvocation(
                    reference,
                    plan["evaluation_level"],
                    caster.id,
                    plan["target_id"],
                    plan["target"],
                    native_context_hex=normal_root_context(
                        execution_origin,
                        caster_id=caster.id,
                        spell_id=plan["spell_id"],
                        level=plan["evaluation_level"],
                    ).hex(),
                )
            )
            for reference in plan["effect_ids"]
        )
    for opcode, payload in effect_packets:
        if (
            type(opcode) is not int
            or not 0 < opcode < 1 << 16
            or not isinstance(payload, bytes)
        ):
            raise ValueError("Invalid effect packet in transaction")
    # Packet source is the actual cast actor, while the connected player's
    # snapshot remains the owner/deck authority for the ordinary player route.
    cast_source = dict(character, id=caster.id)
    packets = (
        (
            12588,
            cast_animation(
                fight.id,
                action_id,
                cast_source,
                plan["spell_id"],
                plan["target"],
                critical=critical,
                native_uid=plan["spell_uid"],
                native_level=plan["evaluation_level"],
            ),
        ),
        (
            12678,
            cast_notification(
                fight.id,
                action_id,
                cast_source,
                plan["spell_id"],
                plan["target"],
                critical=critical,
                native_uid=plan["spell_uid"],
                native_level=plan["evaluation_level"],
            ),
        ),
        *effect_packets,
    )
    from .combat_spell_usage import consume_usage

    consume_usage(preview, plan)
    if caster.effect_stats is not None and 4 in caster.effect_stats:
        wp_remaining = caster.effect_stats[4]
    return SpellTransaction(
        preview,
        plan,
        wp_remaining,
        outcomes,
        packets,
        tuple(preview.events[event_start:]),
        source_state,
        action_id,
    )
