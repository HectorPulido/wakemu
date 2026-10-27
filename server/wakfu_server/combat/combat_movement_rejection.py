"""Owned native13887 correction after an uncommitted12161 request.

Original cvQ/cjD schedules aVk with the canonical position and flushes its
queue. Its owned-current completion clears the pending movement latch via
dbe.fcK/fcJ. This is a position correction, not a successful movement action.
"""
import struct


def movement_rejection_packet(runtime, account_id, body, *, session_is_current=False):
    """Read the fresh current fighter only behind an explicit session fence."""
    if session_is_current is not True:
        return None
    from .combat_movement_runtime import decode_request

    fight = runtime.fight
    if fight.phase != "active" or runtime.awaiting_ack is not None:
        return None
    try:
        actor_id, _ = decode_request(body)
        actor = fight._current_owned(account_id, actor_id)
        position = tuple(actor.position)
        if (
            type(fight.id) is not int
            or not 0 < fight.id < (1 << 31)
            or len(position) != 3
            or any(type(value) is not int for value in position)
        ):
            return None
        payload = struct.pack(">iqiih", fight.id, actor.id, *position)
    except (ValueError, TypeError, struct.error, OverflowError):
        return None
    return 13887, payload


def queue_shared_movement_rejection(registry, session, fight_id, body):
    """Queue one private correction from canonical state under its live lease.

    Presentation recovery owns its own ordered input handoff. Do not introduce
    a correction ahead of pending native births, world return or publication.
    """
    from .combat_shared import Batch

    with registry._locked_fight(fight_id, registry=False) as shared:
        if shared is None:
            return False
        try:
            registry._member(shared, session)
        except ValueError:
            return False
        if (
            shared.runtime.fight is not shared.fight
            or shared.fight.id != fight_id
            or session.account_id in shared.reconnect_presentations
            or session.account_id in shared.pending_world_recoveries
        ):
            return False
        packet = movement_rejection_packet(
            shared.runtime, session.account_id, body, session_is_current=True
        )
        if packet is None:
            return False
        packets = registry._packets((packet,))
        shared.sequence += 1
        registry._queue_recipient(
            shared,
            session.account_id,
            Batch(shared.sequence, packets, public_events=False),
        )
        return True
