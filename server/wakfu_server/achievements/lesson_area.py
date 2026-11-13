"""Qualified simultaneous target sets for the reconstructed Rii area lesson.

An event producer must supply the targets actually selected and hit by one
authenticated spell execution.  A translated objective or a list provided by
the client is never an authoritative hit.  This pure contract does not create
an encounter, apply damage, teleport actors, or award quest progress.
"""

from copy import deepcopy


AREA_EFFECTS = frozenset({367103, 367142, 367145})
REQUIRED_HITS = 4
SACK_COUNT = 4
EFFECT_SEQUENCE = (367142, 367142, 367103, 367145)


def formation(cells, occupied, *, anchor, phase, effects, same_height=True):
    """Find four same-height walkable cells in a native training spell area.

    This is a candidate layout generator, not evidence of the original area's
    placements. A caller must additionally validate combat placement, casting
    distance, line of sight, and publish actual movement using its existing
    spatial authority. Prefer a deterministic small area near the owner.
    """
    from wakfu_server.combat_effect_targets import area_offsets

    if (
        not isinstance(anchor, tuple)
        or len(anchor) != 3
        or any(type(value) is not int for value in anchor)
        or type(phase) is not int
        or not 0 <= phase < REQUIRED_HITS
        or type(same_height) is not bool
    ):
        raise ValueError("Invalid area lesson placement context")
    effect_id = EFFECT_SEQUENCE[phase]
    effect = effects.get(str(effect_id))
    if not isinstance(effect, dict):
        raise ValueError("Missing native area lesson effect")
    offsets = area_offsets(effect)
    blocked = set(occupied) | {anchor}
    available = {
        cell
        for cell in cells
        if isinstance(cell, tuple)
        and len(cell) == 3
        and all(type(value) is int for value in cell)
        and (not same_height or cell[2] == anchor[2])
        and cell not in blocked
        and abs(cell[0] - anchor[0]) + abs(cell[1] - anchor[1]) <= 8
    }
    # All three installed lesson spells have native range 2–16 and do not
    # require line of sight. Never propose an adjacent uncastable center.
    centers = sorted(
        (
            cell
            for cell in available
            if 2 <= abs(cell[0] - anchor[0]) + abs(cell[1] - anchor[1]) <= 16
        ),
        key=lambda cell: (
            abs(cell[0] - anchor[0]) + abs(cell[1] - anchor[1]),
            abs(cell[2] - anchor[2]),
            cell,
        ),
    )
    for center in centers:
        inside = sorted(
            (x, y, center[2])
            for x, y in ((center[0] + dx, center[1] + dy) for dx, dy in offsets)
            if (x, y, center[2]) in available
        )
        if len(inside) >= SACK_COUNT:
            return center, tuple(inside[:SACK_COUNT])
    return None


def observe(
    state, *, owner_id, source_id, target_ids, hit_ids, effect_reference, action_id
):
    """Count a cast only if all four owned sacks were hit in that one cast.

    Both target and hit identities must come from the server's combat preview;
    incomplete casts are left unchanged.  The action identity prevents a
    replay from incrementing progress. The actual layouts and actor references
    are deliberately left to the encounter producer and require separate
    validation against the map and the native area selector.
    """
    if not isinstance(state, dict):
        raise ValueError("Invalid area lesson state")
    if any(
        type(value) is not int or value <= 0
        for value in (owner_id, source_id, action_id)
    ):
        raise ValueError("Invalid area lesson event identity")
    targets = tuple(target_ids)
    hits = tuple(hit_ids)
    if (
        len(targets) != SACK_COUNT
        or len(set(targets)) != SACK_COUNT
        or any(type(value) is not int or value >= 0 for value in targets)
        or any(type(value) is not int for value in hits)
    ):
        raise ValueError("Invalid area lesson target set")
    count = state.get("hits", 0)
    seen = state.get("actions", [])
    if (
        type(count) is not int
        or not 0 <= count <= REQUIRED_HITS
        or not isinstance(seen, list)
        or len(seen) != count
        or len(set(seen)) != len(seen)
        or any(type(value) is not int or value <= 0 for value in seen)
    ):
        raise ValueError("Invalid area lesson progress")
    result = deepcopy(state)
    if (
        count == REQUIRED_HITS
        or action_id in seen
        or source_id != owner_id
        or effect_reference not in AREA_EFFECTS
        or len(hits) != SACK_COUNT
        or len(set(hits)) != SACK_COUNT
        or set(hits) != set(targets)
    ):
        return result
    result["hits"] = count + 1
    result["actions"] = [*seen, action_id]
    return result
