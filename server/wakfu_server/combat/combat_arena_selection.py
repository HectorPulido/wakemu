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


MAX_CELL_BUDGET = 2500


def compact_encounter(data, player, members, cell_budget=None):
    """Local encounter formation on one mutually reachable native component.

    Monster world coordinates are preferences, not mandatory combat positions.
    The player remains anchored. The requested4900-cell budget is independent
    of aspect ratio. Native directed edges and selected heights are preserved,
    including after ambiguous-column removal and budget truncation.
    """
    if cell_budget is None:
        cell_budget = MAX_CELL_BUDGET

    origin = _cell(player)
    originals = [_cell(member) for member in members]
    if not originals or len(originals) > 126:
        raise ValueError("Invalid encounter monster count")
    if type(cell_budget) is not int or not 2 <= cell_budget <= MAX_CELL_BUDGET:
        raise ValueError(
            "Encounter cell budget must be between2 and " + str(MAX_CELL_BUDGET)
        )
    cells = {_cell(cell) for cell in data["cells"]}
    edges = {tuple(map(_cell, edge)) for edge in data["edges"]}
    # Reuse strict topology validation before selecting/repositioning anybody.
    if any(
        a not in cells or b not in cells or abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1
        for a, b in edges
    ):
        raise ValueError("Invalid native encounter topology edge")
    cropped = cells
    if origin not in cropped:
        raise ValueError("Player is outside native encounter terrain")
    reverse = {(b, a) for a, b in edges}
    selected = _reachable(origin, cropped, edges) & _reachable(origin, cropped, reverse)
    columns = defaultdict(list)
    for cell in selected:
        columns[cell[:2]].append(cell)
    ambiguous = {xy for xy, values in columns.items() if len(values) > 1}
    if origin[:2] in ambiguous:
        raise ValueError("Player occupies ambiguous native encounter surface")
    selected = {c for c in selected if c[:2] not in ambiguous}
    selected = _reachable(origin, selected, edges) & _reachable(
        origin, selected, reverse
    )
    # The requested map budget includes blocked rectangle holes, not only
    # playable cells. Native dimensions are int32 and mask count allows32767,
    # but the encounter policy caps both selected cells and the rectangle4900.
    # Flexible shapes such as10x490 remain valid.
    outgoing_full = defaultdict(set)
    for a, b in edges:
        if a in selected and b in selected:
            outgoing_full[a].add(b)
    bounded = {origin}
    queue = deque([origin])
    xmin = xmax = origin[0]
    ymin = ymax = origin[1]
    while queue and len(bounded) < cell_budget:
        current = queue.popleft()
        for target in sorted(outgoing_full[current]):
            if target in bounded:
                continue
            lo_x, hi_x = min(xmin, target[0]), max(xmax, target[0])
            lo_y, hi_y = min(ymin, target[1]), max(ymax, target[1])
            if (hi_x - lo_x + 1) * (hi_y - lo_y + 1) > cell_budget:
                continue
            bounded.add(target)
            queue.append(target)
            xmin, xmax, ymin, ymax = lo_x, hi_x, lo_y, hi_y
            if len(bounded) == cell_budget:
                break
    selected = _reachable(origin, bounded, edges) & _reachable(origin, bounded, reverse)
    if len(selected) <= len(originals):
        raise ValueError(
            "Native reachable encounter component lacks participant capacity"
        )
    outgoing = defaultdict(set)
    for a, b in edges:
        if a in selected and b in selected:
            outgoing[a].add(b)
    distances = {origin: 0}
    pending = deque([origin])
    while pending:
        current = pending.popleft()
        for target in sorted(outgoing[current]):
            if target not in distances:
                distances[target] = distances[current] + 1
                pending.append(target)
    free = selected - {origin}
    relocated = []
    for original in originals:
        if original in free:
            chosen = original
        else:
            # Compact opposing formation around six native path steps; source
            # position breaks ties without expanding the fight to world groups.
            chosen = min(
                free,
                key=lambda c: (
                    abs(distances[c] - 6),
                    abs(c[0] - original[0]) + abs(c[1] - original[1]),
                    c,
                ),
            )
        relocated.append(chosen)
        free.remove(chosen)
    chosen_edges = {(a, b) for a, b in edges if a in selected and b in selected}
    return dict(
        map_id=data["map_id"],
        cells=selected,
        edges=chosen_edges,
        placement={0: [origin], 1: relocated},
        participant_positions=list(zip(originals, relocated)),
        blocked_ambiguous=ambiguous,
        bounds=(
            min(c[0] for c in selected),
            min(c[1] for c in selected),
            max(c[0] for c in selected),
            max(c[1] for c in selected),
        ),
    )


def cardinal_border_cells(cells):
    """Explicit local perimeter: selected XYZ with a missing cardinal XY."""
    cells = {_cell(cell) for cell in cells}
    xy = {cell[:2] for cell in cells}
    return frozenset(
        cell
        for cell in cells
        if any(
            (cell[0] + dx, cell[1] + dy) not in xy
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
    )
