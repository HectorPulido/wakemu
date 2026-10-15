"""Shared client-equivalent QI cell passability for walking and NPC planning."""


def movement_blocked_cells(fight, actor, cells):
    """Return QI-blocked candidate cells, or None when native QI is unknown.

    QI.g checks arena mask bits before its movement override. The override then
    bypasses QK occupancy only; otherwise bcP movement blockers are considered
    except the moving actor's own byte and temporary biN exclusions.
    """
    if getattr(fight, "native_qi_slots", None) is None and not hasattr(
        fight, "native_pointer_checkpoint"
    ):
        return None

    from .combat_qi_fight import current_registry

    registry = current_registry(fight)
    qi = registry.snapshot()
    override = getattr(fight, "native_qi_movement_override", None)
    ignored = getattr(fight, "native_qi_ignored_slots", None)
    own_slot = getattr(actor, "native_obstacle_id", None)
    if (
        type(override) is not bool
        or not isinstance(ignored, (tuple, list))
        or any(type(slot) is not int or not 0 <= slot <= 126 for slot in ignored)
        or type(own_slot) is not int
        or not -1 <= own_slot <= 126
        or own_slot >= 0
        and (
            registry.slots[own_slot] is None
            or registry.slots[own_slot]["identity"] != ["actor", actor.id]
        )
    ):
        raise ValueError("Missing actual native QI movement flags")

    blocked = set()
    for cell in cells:
        x, y = cell[:2]
        index = qi._int32(
            qi._int32(qi._int32(y - qi.y) * qi.width) + qi._int32(x - qi.x)
        )
        # Exact QI.g order: mask rejection precedes biP occupancy bypass.
        if not 0 <= index < len(qi.masks) or qi.masks[index] & 768:
            blocked.add(cell)
            continue
        if override:
            continue
        if any(
            slot != own_slot
            and slot not in ignored
            and registry.slots[slot] is not None
            and registry.slots[slot]["movement_blocking"]
            for slot in (qi.U(x, y) or ())
        ):
            blocked.add(cell)
    return blocked
