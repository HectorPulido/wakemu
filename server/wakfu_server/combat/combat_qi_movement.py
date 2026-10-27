"""Shared client-equivalent QI cell passability for walking and NPC planning."""


def movement_blocked_cells(fight, actor, cells):
    """Return blocked mover anchors using each complete destination footprint.

    Unknown legacy point-only populations retain the None fallback contract.

    QI.g checks arena mask bits before its movement override. The override then
    bypasses QK occupancy only; otherwise bcP movement blockers are considered
    except the moving actor's own byte and temporary biN exclusions.
    """
    if getattr(fight, "native_qi_slots", None) is None and not hasattr(
        fight, "native_pointer_checkpoint"
    ):
        return _legacy_footprint_blocked_cells(fight, actor, cells)

    from .combat_qi_fight import current_registry
    from .combat_pointer_qi_registry import registered_obstacle, registered_population

    registry = current_registry(fight)
    qi, population = registered_population(registry)
    override = getattr(fight, "native_qi_movement_override", None)
    ignored = getattr(fight, "native_qi_ignored_slots", None)
    own_slot = getattr(actor, "native_obstacle_id", None)
    own_row = (
        registered_obstacle(registry, own_slot)
        if type(own_slot) is int and 0 <= own_slot <= 126
        else None
    )
    if (
        type(override) is not bool
        or not isinstance(ignored, (tuple, list))
        or any(type(slot) is not int or not 0 <= slot <= 126 for slot in ignored)
        or type(own_slot) is not int
        or not -1 <= own_slot <= 126
        or own_slot >= 0
        and (own_row is None or own_row["identity"] != ["actor", actor.id])
    ):
        raise ValueError("Missing actual native QI movement flags")

    radius = (
        own_row["radius"] if own_slot >= 0 else getattr(actor, "physical_radius", None)
    )
    if radius is None:
        radius = 0  # Legacy unregistered point-actor fixtures.
    declared_radius = getattr(actor, "physical_radius", None)
    if (
        type(radius) is not int
        or not -128 <= radius <= 127
        or declared_radius is not None
        and declared_radius != radius
    ):
        raise ValueError("Missing actual native QI movement footprint")
    radius = max(0, radius)
    blocked = set()
    for cell in cells:
        x0, y0 = cell[:2]
        if any(
            not -(1 << 31) <= bound < (1 << 31) - 1
            for bound in (x0 - radius, x0 + radius, y0 - radius, y0 + radius)
        ):
            raise ValueError(
                "Unsupported native movement footprint coordinate overflow"
            )
        # adO passes bcL to Sn.boC. Sn tests each translated square cell
        # through VE.aK then VE.g/QI.g, not only the mover's anchor.
        for x in range(x0 - radius, x0 + radius + 1):
            for y in range(y0 - radius, y0 + radius + 1):
                index = qi._int32(
                    qi._int32(qi._int32(y - qi.y) * qi.width) + qi._int32(x - qi.x)
                )
                if (
                    not qi.aK(x, y)
                    or not 0 <= index < len(qi.masks)
                    or qi.masks[index] & 768
                ):
                    blocked.add(cell)
                    break
                # Exact QI.g order: terrain rejection precedes biP override.
                if not override and any(
                    slot != own_slot
                    and slot not in ignored
                    and (row := registered_obstacle(registry, slot)) is not None
                    and row["movement_blocking"]
                    for slot in population(x, y)
                ):
                    blocked.add(cell)
                    break
            if cell in blocked:
                break
    return blocked


def _legacy_footprint_blocked_cells(fight, actor, cells):
    """Keep fixture fallback occupancy complete when actual radii are known.

    Native QI masks, override and ignored slots always take the primary path.
    Unknown legacy point-only populations retain their existing None contract.
    """
    actors = tuple(fight.actors.values())
    if not any((getattr(other, "physical_radius", None) or 0) > 0 for other in actors):
        return None
    from .combat_obstacle_condition import footprint

    occupied = {
        cell
        for other in actors
        if other.id != actor.id and other.hp > 0
        for cell in footprint(
            other.position, getattr(other, "physical_radius", None) or 0
        )
    }
    walkable = {cell[:2] for cell in fight.walkable}
    radius = getattr(actor, "physical_radius", None) or 0
    return {
        center
        for center in cells
        if any(
            cell not in walkable or cell in occupied
            for cell in footprint(center, radius)
        )
    }
