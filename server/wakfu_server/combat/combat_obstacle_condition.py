"""Native eOp: dynamic QI.V object flags, with an explicit viewer anchor.

Ordinary registered fight actors use big/eGj obstacle contracts. No HP,
walkability or floor height is substituted for native obstacle membership.
"""


def blocking_flags(properties, *, viewer_ally):
    if not isinstance(properties, (set, frozenset)) or type(viewer_ally) is not bool:
        raise ValueError("Missing native viewer/obstacle property authority")
    visible = 18 not in properties and (6 in properties or 5 not in properties)
    return viewer_ally or visible, visible and 54 not in properties


def footprint(position, radius, *, query=False):
    if type(radius) is not int or not -128 <= radius <= 127:
        raise ValueError("Invalid native signed-byte obstacle radius")
    x, y = position[:2]
    if radius <= 0:
        return ((x, y),)
    # QI registration includes upper bound; eOp scanning excludes it.
    end = radius if query else radius + 1
    return tuple(
        (x + dx, y + dy) for dx in range(-radius, end) for dy in range(-radius, end)
    )


def is_obstacle(fight, *, selected_id, viewer_id, actor_authority):
    if selected_id is None:
        return False  # eOp null selected eHg, with no ePy fallback in this entry.
    selected = fight.actors.get(selected_id)
    if selected is None:
        return False  # A supplied Qq/cell is not the selected ordinary fighter.
    if fight.phase != "active":
        raise ValueError("Missing native dnz active fight membership")
    if viewer_id not in fight.actors:
        raise ValueError("Missing explicit native obstacle viewer")
    static = getattr(fight, "native_obstacle_cells", None)
    if static is None or static:
        raise ValueError("Missing complete native static QK flag population")
    viewer = fight.actors[viewer_id]
    actor_authority(fight, viewer)
    terrain = getattr(fight, "walkable", None)
    if not terrain:
        raise ValueError("Missing native serialized QI bounds")
    x0, x1 = min(c[0] for c in terrain), max(c[0] for c in terrain)
    y0, y1 = min(c[1] for c in terrain), max(c[1] for c in terrain)
    in_bounds = lambda cell: x0 <= cell[0] <= x1 and y0 <= cell[1] <= y1
    query = tuple(
        cell
        for cell in footprint(selected.position, selected.physical_radius, query=True)
        if in_bounds(cell)
    )
    candidates = {cell: [] for cell in query}
    for actor in fight.actors.values():
        metadata = actor_authority(fight, actor)
        if metadata.targeting.get("is_eHH") is not True:
            raise ValueError("Missing native big obstacle class authority")
        properties = frozenset(actor_authority.properties(fight, actor))
        affiliation = getattr(actor, "native_fight_affiliation", actor.team)
        viewer_affiliation = getattr(viewer, "native_fight_affiliation", viewer.team)
        if any(
            type(value) is not int or not -128 <= value < 128
            for value in (affiliation, viewer_affiliation)
        ):
            raise ValueError("Missing native signed-byte viewer affiliation")
        flags = blocking_flags(
            properties, viewer_ally=affiliation == viewer_affiliation
        )
        outcome = any(flags)
        for cell in footprint(actor.position, actor.physical_radius):
            if in_bounds(cell) and cell in candidates:
                candidates[cell].append(outcome)
    ambiguous = False
    for outcomes in candidates.values():
        # QI.V chooses one QK via native Trove iteration. An overlap is exact
        # when all possibilities agree; mixed flags require its actual order.
        if outcomes and all(outcomes):
            return True
        if outcomes and any(outcomes):
            ambiguous = True
    if ambiguous:
        raise ValueError("Ambiguous native overlapping QK iteration order")
    return False
