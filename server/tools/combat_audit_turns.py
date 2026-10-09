"""Offline audit routing through the actual owned end/ACK runtime boundary."""
import struct


def advance_actual_turn(runtime):
    actor = runtime.fight.current
    if actor is None:
        raise ValueError("Audit turn requires actual current actor")
    packets = (
        runtime.end_turn(actor.owner_id, actor.id, actor.turn_count)
        if actor.controlled
        else runtime.end_server_turn(actor.id, runtime.fight.turn_id)
    )
    pending = runtime.awaiting_ack
    if pending is not None:
        packets += runtime.acknowledge_turn(struct.pack(">i", pending))
    return packets
