"""Native 13624 STANDARD animation, verified against cvP/amK/cjA.

Path includes the initial cell, followed by each destination. The client's
movement action checks its first point against the actor's current position.
Caller owns geometry validation and ordered action/flush scheduling.
"""
import struct


def movement(fight_id, action_id, actor_id, points, direction, parent_action_id=-1):
    points = [tuple(point) for point in points]
    if not 2 <= len(points) <= 6553:
        raise ValueError("Movement requires origin and destinations within amK bounds")
    if type(direction) is not int or not 0 <= direction <= 7:
        raise ValueError("Invalid direction")
    if any(len(point) != 3 for point in points):
        raise ValueError("Invalid movement cell")
    body = struct.pack(
        ">iiiqBB", fight_id, action_id, parent_action_id, actor_id, direction, 0
    )
    body += b"".join(struct.pack(">iih", *point) for point in points)
    return 13624, body


def portal_movement(fight_id, action_id, actor_id, origin, destination, direction):
    """Original fcC.USE_GATE_TELEPORT ordinal3, cvP13624 ->cjA/aVw.

    amK.bDW supplies the final destination; aVw preserves actor facing.
    Keep the ordinary STANDARD writer unchanged.
    """
    opcode, body = movement(
        fight_id, action_id, actor_id, [origin, destination], direction
    )
    return opcode, body[:21] + b"\x03" + body[22:]
