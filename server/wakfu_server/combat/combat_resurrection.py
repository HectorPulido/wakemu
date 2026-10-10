"""Owned eXO restoration and native aTS1 put-fighter-back-in-play boundary.

Original aTS1 calls buH.be -> fbX.D -> fem.rD and fcb.D -> fdt.bu.
The original server publisher is unavailable; coupling a successful flagged196
HP restoration to this inverse lifecycle is explicit Wakemu server policy.
"""
import struct


def prepare_resurrection(fight, target, effect):
    """Capture an actual revivable OFF_PLAY fighter before any PA assignment."""
    if 15 not in effect.get("native_effect_flags", ()):
        return None
    from .combat_global_pv_collections import global_fighter_guards
    from .combat_ordinary_death import registered_ordinary_death
    from .combat_qi_fight import current_registry

    if not hasattr(fight, "native_global_pv_collections"):
        return None
    guards = global_fighter_guards(fight, target.id)
    if not guards["baG"]:
        return None  # IN_PLAY restoration is ordinary; OUT_OF_PLAY is final.
    if target.hp != 0 or not registered_ordinary_death(fight, target):
        raise ValueError("Resurrection requires an actual owned OFF_PLAY corpse")
    registry = current_registry(fight)
    slot = target.native_obstacle_id
    if (
        type(slot) is not int
        or not 0 <= slot < len(registry.slots)
        or registry.slots[slot] is None
        or registry.slots[slot]["identity"] != ["actor", target.id]
        or registry.slots[slot]["position"] != list(target.position[:2])
    ):
        raise ValueError("Revivable fighter lost its owned QI slot")
    removed = [
        row for row in fight.native_timeline_removed if row["actor_id"] == target.id
    ]
    if target.id in fight.order:
        if removed:
            raise ValueError("Inconsistent live and removed resurrection timeline")
        return dict(slot=slot, removed=None)
    if len(removed) != 1 or removed[0]["modifications"]:
        raise ValueError("Missing native saved resurrection timeline position")
    return dict(slot=slot, removed=dict(removed[0]))


def complete_resurrection(fight, target, prepared, *, action_id, packets):
    if prepared is None or target.hp <= 0:
        return False
    from .combat_global_pv_collections import set_global_fighter_status
    from .combat_native_death_status import apply_native_fighter_state_transition
    from .combat_timeline_snapshot import insert

    current_id = fight.current.id
    row = prepared["removed"]
    if row is not None:
        # fem.rD consumes its saved feu and reinserts at that position.
        slot = min(row["position"], len(fight.order))
        insert(fight, target.id, slot)
        fight.order.insert(slot, target.id)
        fight.turn_index = fight.order.index(current_id)
        fight.native_timeline_removed = [
            item
            for item in fight.native_timeline_removed
            if item["actor_id"] != target.id
        ]
        if fight.native_base_turn_order is not None:
            base = list(fight.native_base_turn_order)
            if target.id not in base:
                base.insert(min(slot, len(base)), target.id)
            fight.native_base_turn_order = tuple(base)
    set_global_fighter_status(fight, target.id, "IN_PLAY")
    apply_native_fighter_state_transition(target, 1)
    fight._event("resurrection", actor_id=target.id, hp=target.hp)
    packets.append(
        (12727, struct.pack(">iiiqB", fight.id, action_id, -1, target.id, 1))
    )
    return True
