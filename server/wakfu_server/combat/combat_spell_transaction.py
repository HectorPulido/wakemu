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
    wp_remaining = wp_current - plan["costs"]["wp"]
    if caster.effect_stats is not None and 4 in caster.effect_stats:
        if caster.effect_stats[4] != wp_current:
            raise ValueError("WP snapshot disagrees with authoritative resource")
        caster.effect_stats[4] = wp_remaining
    caster.ap -= plan["costs"]["ap"]
    caster.mp -= plan["costs"]["mp"]
    if caster.effect_stats is not None:
        for stat, value in ((2, caster.ap), (3, caster.mp)):
            if stat in caster.effect_stats:
                caster.effect_stats[stat] = value
    mirror_cast_facing(caster, plan)
    dispatcher, effect_packets = runtime_factory(preview, plan)
    if not isinstance(dispatcher, EffectDispatcher) or not isinstance(
        effect_packets, list
    ):
        raise ValueError(
            "Runtime factory must return dispatcher and private packet list"
        )
    with active_spell_scope(preview, plan["spell_id"]), preview.effect_resolution():
        outcomes = tuple(
            dispatcher.execute(
                EffectInvocation(
                    reference,
                    plan["evaluation_level"],
                    caster.id,
                    plan["target_id"],
                    plan["target"],
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
    packets = (
        (
            12588,
            cast_animation(
                fight.id,
                action_id,
                character,
                plan["spell_id"],
                plan["target"],
                critical=critical,
                native_uid=plan["spell_uid"]
                if plan["spell_uid"] == plan["spell_id"]
                else None,
                native_level=plan["evaluation_level"],
            ),
        ),
        (
            12678,
            cast_notification(
                fight.id,
                action_id,
                character,
                plan["spell_id"],
                plan["target"],
                critical=critical,
                native_uid=plan["spell_uid"]
                if plan["spell_uid"] == plan["spell_id"]
                else None,
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
