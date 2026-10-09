"""Pure turn-packet coordination helpers for the three-peer TLS harness."""

import struct
import time


def decode_turn(body, fight_id, allowed_actor_ids, *, after_action_id=0):
    if len(body) < 28:
        raise AssertionError("truncated native 13482 turn-start packet")
    packet_fight_id, action_id, sentinel = struct.unpack_from(">iii", body)
    actor_id = struct.unpack_from(">q", body, 12)[0]
    if packet_fight_id != fight_id or sentinel != -1:
        raise AssertionError("turn-start packet has wrong fight prefix")
    if action_id <= after_action_id:
        raise AssertionError("turn-start action sequence did not advance")
    if actor_id not in allowed_actor_ids:
        raise AssertionError("turn-start names an absent/withdrawn actor")
    return action_id, actor_id


def initial_survivor_turns(
    withdraw_phase,
    peer_b,
    peer_c,
    fight_id,
    survivor_ids,
    withdrawn_ids,
    ack_turn=1,
    *,
    timeout=40,
):
    """Return matching survivor starts and the next ACK sequence value."""
    if withdraw_phase == "placement":
        turn_b, _ = peer_b.wait(13482, timeout=timeout)
        turn_c, _ = peer_c.wait(13482, timeout=timeout)
        if turn_b != turn_c:
            raise AssertionError("surviving owners received different initial turns")
        decode_turn(turn_b, fight_id, set(survivor_ids))
        return turn_b, turn_c, ack_turn
    if withdraw_phase != "active":
        raise ValueError("withdraw_phase must be placement or active")

    accepted_ids = set(survivor_ids) | set(withdrawn_ids)
    deadline = time.monotonic() + timeout
    last_action_id = 0
    while time.monotonic() < deadline:
        timeout_left = max(0.1, deadline - time.monotonic())
        (opcode_b, body_b), _ = peer_b.wait_any(
            {12502, 12755, 13482}, timeout=timeout_left
        )
        timeout_left = max(0.1, deadline - time.monotonic())
        (opcode_c, body_c), _ = peer_c.wait_any(
            {12502, 12755, 13482}, timeout=timeout_left
        )
        if opcode_b != opcode_c:
            raise AssertionError("survivors received different turn transitions")
        if opcode_b == 12755:
            raise AssertionError("shared fight ended before survivors resumed turns")
        if opcode_b == 12502:
            peer_b.send(13510, struct.pack(">i", ack_turn))
            peer_c.send(13510, struct.pack(">i", ack_turn))
            ack_turn += 1
            continue
        if body_b != body_c:
            raise AssertionError("survivors received different active turn packets")
        last_action_id, actor_id = decode_turn(
            body_b, fight_id, accepted_ids, after_action_id=last_action_id
        )
        if actor_id in survivor_ids:
            return body_b, body_c, ack_turn
    raise AssertionError("no active turn was pushed to a surviving owner")
