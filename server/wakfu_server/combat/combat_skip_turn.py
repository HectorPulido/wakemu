"""Wakemu scheduling policy: native SKIP_TURN ends the actual actor turn.

Consume the live property after start reactions and expiry. End reactions,
state clocks, resource refill and synchronization use the ordinary turn APIs.
Do not remove the property or its state carrier; native expiry owns them.
"""


def skip_turn_required(actor):
    from .combat_property_stack import property_present

    counts = getattr(actor, "native_fight_property_counts", None)
    if counts is not None:
        return property_present(counts, 1)
    properties = getattr(actor, "native_fight_properties", None)
    return properties is not None and 1 in properties


def skip_turn_packets(runtime):
    fight = runtime.fight
    actor = fight.current
    if fight.phase != "active" or actor is None or not skip_turn_required(actor):
        return None
    if runtime.awaiting_ack is not None:
        raise ValueError("Cannot skip an unsynchronized actor turn")
    from .combat_effective_control import (
        effective_input_owner,
        effective_server_controlled,
    )
    from .combat_timeline_snapshot import current_wire_turn

    fight._event(
        "turn_skipped",
        actor_id=actor.id,
        turn_id=fight.turn_id,
        property_id=1,
        policy="wakemu-live-skip-turn-v1",
    )
    if effective_server_controlled(fight, actor):
        return runtime.end_server_turn(actor.id, fight.turn_id)
    owner = effective_input_owner(fight, actor)
    if owner is None:
        raise ValueError("Missing actual skipped-turn owner")
    return runtime.end_turn(owner, actor.id, current_wire_turn(fight))
