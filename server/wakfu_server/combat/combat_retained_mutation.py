"""Shared retirement of owned retained effects and their actual Qf delivery.

Native reversal remains with each concrete handler. Group retirement preserves
its historical packet-before-queue-before-registration ordering; executed child
effects keep their separate ownership and are not implicitly reversed here.
"""
from dataclasses import dataclass
import struct
from .combat_effect_removal import running_effect_removal
from .combat_retained_effects import RetainedEffect


@dataclass(frozen=True)
class GroupRetirement:
    uid: int
    packet: bytes


def plan_group_retirement(fight, *, action_id, uid):
    row = fight.native_owned_group_effects.get(uid)
    metadata = fight.native_retained_records.get(uid)
    if row is None or metadata is None:
        raise ValueError("Missing centrally owned native group")
    entry = RetainedEffect(**metadata)
    packet = running_effect_removal(
        fight.id,
        action_id,
        effect_class=row["effect_class"],
        target_id=entry.manager_id if row["target_id"] is None else row["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    manager = entry.manager_id if entry.manager_id is not None else entry.target_id
    return GroupRetirement(uid, packet[:-16] + struct.pack(">qq", manager, uid))


def retire_group(fight, packets, *, action_id, uid):
    plan = plan_group_retirement(fight, action_id=action_id, uid=uid)
    packets.append((13560, plan.packet))
    from .combat_native_delay_queue import cancel

    if hasattr(fight, "native_delay_queue"):
        cancel(fight.native_delay_queue, plan.uid)
    del fight.native_owned_group_effects[plan.uid]
    del fight.native_retained_records[plan.uid]
    fight.native_retained_order.remove(plan.uid)


def retire_stat(handler, uid):
    row = handler.fight.owned_stat_effects.get(uid)
    if row is None:
        raise ValueError("Missing owned native stat removal")
    metadata = handler.fight.native_retained_records.get(uid)
    manager = row["target_id"] if metadata is None else metadata.get("manager_id")
    if manager is None:
        raise ValueError("Missing native retained stat manager identity")
    handler.remove(uid)
    if manager != row["target_id"]:
        opcode, packet = handler.packets[-1]
        if opcode != 13560 or struct.unpack(">q", packet[-8:])[0] != uid:
            raise ValueError("Native stat removal outbox identity differs")
        handler.packets[-1] = (opcode, packet[:-16] + struct.pack(">qq", manager, uid))
