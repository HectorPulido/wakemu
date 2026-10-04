"""Bounded arena selection using only exported native directed map edges.

Stacked floors disconnected from the player are not confused with reachable
floors. Columns with multiple reachable heights remain blocked; no height or
movement connection is invented to accommodate a fight participant.
"""
from collections import defaultdict, deque


def _cell(value):
    if isinstance(value, dict):
        value = value.get("position", (value.get("x"), value.get("y"), value.get("z")))
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("Invalid arena participant or topology coordinate")
    x, y, z = value
    if (
        any(type(n) is not int for n in value)
        or not -(1 << 31) <= x < (1 << 31)
        or not -(1 << 31) <= y < (1 << 31)
        or not -(1 << 15) <= z < (1 << 15)
    ):
        raise ValueError("Arena coordinate is outside native bounds")
    return x, y, z


def _reachable(origin, cells, edges):
    outgoing = defaultdict(set)
    for start, end in edges:
        if start in cells and end in cells:
            outgoing[start].add(end)
    reached = {origin}
    pending = deque([origin])
    while pending:
        for target in outgoing[pending.popleft()]:
            if target not in reached:
                reached.add(target)
                pending.append(target)
    return reached


def bounded_arena(data, player, members, radius=12):
    """Select one safe altitude per XY and placements for every supplied NPC.

    Coordinates or dictionaries with position/x,y,z are accepted. Radius is a
    Chebyshev window around the player. All monster positions must be reachable
    within the cropped arena; no relocation or guessed alternate floor occurs.
    """
    if not isinstance(data, dict) or type(data.get("map_id")) is not int:
        raise ValueError("Arena requires exported map metadata")
    if type(radius) is not int or not 1 <= radius <= 89:
        raise ValueError("Arena radius exceeds native rectangle limits")
    origin = _cell(player)
    members = [_cell(member) for member in members]
    if not members or len(members) > 126 or len({origin, *members}) != len(members) + 1:
        raise ValueError("Fight participants overlap or exceed native roster limits")
    cells = {_cell(cell) for cell in data["cells"]}
    edges = set()
    for edge in data["edges"]:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            raise ValueError("Invalid native topology edge")
        start, end = map(_cell, edge)
        if (
            start not in cells
            or end not in cells
            or abs(start[0] - end[0]) + abs(start[1] - end[1]) != 1
        ):
            raise ValueError("Native topology edge is missing or nonadjacent")
        edges.add((start, end))
    cropped = {
        cell
        for cell in cells
        if max(abs(cell[0] - origin[0]), abs(cell[1] - origin[1])) <= radius
    }
    if origin not in cropped or any(member not in cropped for member in members):
        raise ValueError("Participant is outside exported walkable arena bounds")
    reached = _reachable(origin, cropped, edges)
    columns = defaultdict(list)
    for cell in reached:
        columns[cell[:2]].append(cell)
    ambiguous = {xy for xy, heights in columns.items() if len(heights) > 1}
    if origin[:2] in ambiguous or any(member[:2] in ambiguous for member in members):
        raise ValueError("Participant occupies an ambiguous reachable floor")
    selected = {cell for cell in reached if cell[:2] not in ambiguous}
    # Removing an ambiguous bridge may detach otherwise reachable cells.
    selected = _reachable(origin, selected, edges)
    if any(member not in selected for member in members):
        raise ValueError("Monster group is unreachable in the safe bounded arena")
    chosen_edges = {
        (start, end) for start, end in edges if start in selected and end in selected
    }
    xmin, xmax = min(c[0] for c in selected), max(c[0] for c in selected)
    ymin, ymax = min(c[1] for c in selected), max(c[1] for c in selected)
    if (xmax - xmin + 1) * (ymax - ymin + 1) > 32767:
        raise ValueError("Arena rectangle exceeds native wire bounds")
    return dict(
        map_id=data["map_id"],
        cells=selected,
        edges=chosen_edges,
        placement={0: [origin], 1: members},
        bounds=(xmin, ymin, xmax, ymax),
        blocked_ambiguous=ambiguous,
    )
