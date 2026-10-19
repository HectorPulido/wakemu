"""Owned combat orientation: coZ13655 -> cvL13494 -> cjx/aTU.

Native UI requests four cardinal orientations. The presentation action changes
facing only; it does not debit AP/MP or use the world position packet13530.
"""
import struct

CARDINAL_DIRECTIONS = frozenset((1, 3, 5, 7))
# Fresh controlled fighters need a tactical facing before their first movement.
# EAST (0) is a world direction, but transformed rigs can lack its idle clip.
# Use a supported cardinal default; subsequent native facing stays authoritative.
INITIAL_PLAYER_DIRECTION = 1


def decode_request(body):
    if not isinstance(body, bytes) or len(body) != 9:
        raise ValueError("Invalid combat orientation request")
    identity, direction = struct.unpack(">qB", body)
    if identity == 0 or direction not in CARDINAL_DIRECTIONS:
        raise ValueError("Invalid combat actor or native cardinal direction")
    return identity, direction


def response(fight_id, action_id, actor_id, direction, sequence=-1):
    return _response(
        fight_id, action_id, actor_id, direction, sequence, CARDINAL_DIRECTIONS
    )


def facing_response(fight_id, action_id, actor_id, direction, sequence=-1):
    """cvL/aTU accepts all eight aAS directions, unlike coZ UI requests."""
    return _response(fight_id, action_id, actor_id, direction, sequence, range(8))


def _response(fight_id, action_id, actor_id, direction, sequence, directions):
    if (
        type(fight_id) is not int
        or not -(1 << 31) <= fight_id < (1 << 31)
        or type(action_id) is not int
        or not 0 < action_id < (1 << 31)
        or type(actor_id) is not int
        or actor_id == 0
        or not -(1 << 63) <= actor_id < (1 << 63)
        or type(direction) is not int
        or direction not in directions
        or type(sequence) is not int
        or not -(1 << 31) <= sequence < (1 << 31)
    ):
        raise ValueError("Invalid native combat orientation response")
    return 13494, struct.pack(
        ">iiiqB", fight_id, action_id, sequence, actor_id, direction
    )


def apply(runtime, owner_id, body):
    identity, direction = decode_request(body)
    fight = runtime.fight
    if runtime.awaiting_ack is not None:
        raise ValueError("Orientation requires synchronized combat state")
    if fight.phase == "placement":
        actor = fight._owned(owner_id, identity)
        if owner_id in fight.ready_owners:
            raise ValueError("Placement is already ready")
        if tuple(actor.position) not in fight.placement[actor.team]:
            raise ValueError("Actor is outside its placement area")
    elif fight.phase == "active":
        actor = fight._current_owned(owner_id, identity)
    else:
        raise ValueError("Orientation requires placement or an active turn")
    next_action = runtime.action_id + 1
    packet = response(fight.id, next_action, identity, direction)
    # Everything validates before changing actor facing or action counters.
    from .combat_carrying import set_registered_direction

    set_registered_direction(fight, actor, direction)
    runtime.action_id = next_action
    event = fight._event(
        "orientation", actor_id=identity, direction=direction, cost_ap=0, cost_mp=0
    )
    return dict(packets=[packet, runtime._flush()], event=event, direction=direction)
