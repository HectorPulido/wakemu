"""Read physical fighter lifecycle state without registering or repairing it."""
from copy import deepcopy


def actor_lifecycle_observables(fight, actor):
    """Snapshot fdy, QI and Tc/SY state, excluding receipts and RNG bookkeeping."""
    collections = getattr(fight, "native_global_pv_collections", None)
    statuses = (
        collections.get("fighter_status", {}) if isinstance(collections, dict) else {}
    )
    slots = getattr(fight, "native_qi_slots", None)
    if hasattr(fight, "native_pointer_checkpoint"):
        from .combat_qi_fight import current_registry

        slots = current_registry(fight).slots
    slot = getattr(actor, "native_obstacle_id", None)
    qi_entry = (
        slots[slot]
        if isinstance(slots, (list, tuple))
        and type(slot) is int
        and 0 <= slot < len(slots)
        else None
    )
    counters = getattr(fight, "native_timeline_member_counters", None)
    key = str(actor.id)
    member = isinstance(counters, dict) and key in counters
    order = fight.order
    return dict(
        fighter_status=statuses.get(key),
        qi_slot=slot,
        qi_entry=deepcopy(qi_entry),
        timeline_member=member,
        timeline_progress=counters[key] if member else None,
        timeline_position=order.index(actor.id) if actor.id in order else None,
    )
