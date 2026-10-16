"""Bounded arena selection using only exported native directed map edges.

Stacked floors disconnected from the player are not confused with reachable
floors. Columns with multiple reachable heights remain blocked; no height or
movement connection is invented to accommodate a fight participant.
"""
from collections import OrderedDict, defaultdict, deque
from threading import RLock
from .combat_geometry import (
    coordinate as _cell,
    PreparedGeometry,
    prepare_geometry,
    reachable,
    edges_within,
    encounter_component,
)


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
    if type(radius) is not int or not 1 <= radius <= 89:
        raise ValueError("Arena radius exceeds native rectangle limits")
    origin = _cell(player)
    members = [_cell(member) for member in members]
    if not members or len(members) > 126 or len({origin, *members}) != len(members) + 1:
        raise ValueError("Fight participants overlap or exceed native roster limits")
    geometry = prepare_geometry(data)
    cells = geometry.cells
    cropped = {
        cell
        for cell in cells
        if max(abs(cell[0] - origin[0]), abs(cell[1] - origin[1])) <= radius
    }
    if origin not in cropped or any(member not in cropped for member in members):
        raise ValueError("Participant is outside exported walkable arena bounds")
    reached = reachable(origin, cropped, geometry.outgoing)
    columns = defaultdict(list)
    for cell in reached:
        columns[cell[:2]].append(cell)
    ambiguous = {xy for xy, heights in columns.items() if len(heights) > 1}
    if origin[:2] in ambiguous or any(member[:2] in ambiguous for member in members):
        raise ValueError("Participant occupies an ambiguous reachable floor")
    selected = {cell for cell in reached if cell[:2] not in ambiguous}
    # Removing an ambiguous bridge may detach otherwise reachable cells.
    selected = reachable(origin, selected, geometry.outgoing)
    if any(member not in selected for member in members):
        raise ValueError("Monster group is unreachable in the safe bounded arena")
    chosen_edges = edges_within(selected, geometry.outgoing)
    xmin, xmax = min(c[0] for c in selected), max(c[0] for c in selected)
    ymin, ymax = min(c[1] for c in selected), max(c[1] for c in selected)
    if (xmax - xmin + 1) * (ymax - ymin + 1) > 32767:
        raise ValueError("Arena rectangle exceeds native wire bounds")
    return dict(
        map_id=geometry.map_id,
        cells=selected,
        edges=chosen_edges,
        placement={0: [origin], 1: members},
        bounds=(xmin, ymin, xmax, ymax),
        blocked_ambiguous=ambiguous,
    )


MAX_CELL_BUDGET = 2500
MIN_ENCOUNTER_CELLS = 25


def _bounds(cells):
    return (
        min(c[0] for c in cells),
        min(c[1] for c in cells),
        max(c[0] for c in cells),
        max(c[1] for c in cells),
    )


def _rectangle_area(bounds):
    xmin, ymin, xmax, ymax = bounds
    return (xmax - xmin + 1) * (ymax - ymin + 1)


def _preferred_originals(origin, originals, cells, budget):
    """Keep reachable original positions whose combined rectangle can fit."""
    preferred = {origin}
    for original in originals:
        if original in cells:
            candidate = preferred | {original}
            if _rectangle_area(_bounds(candidate)) <= budget:
                preferred = candidate
    return preferred


def _rectangular_encounter(origin, preferred, cells, geometry, minimum, target, budget):
    """Prefer native rectangular crops, never inventing cells in their holes."""
    limits = _bounds(cells)
    xmin, ymin, xmax, ymax = _bounds(preferred)
    bounds = (
        max(limits[0], xmin - 1),
        max(limits[1], ymin - 1),
        min(limits[2], xmax + 1),
        min(limits[3], ymax + 1),
    )
    if _rectangle_area(bounds) > budget:
        bounds = (xmin, ymin, xmax, ymax)
    by_xy = {(x, y): (x, y, z) for x, y, z in cells}
    # Native walls may make padding impossible. Never move the player or
    # invent a floor to turn such a wall into a fight perimeter.
    padded_preferred = {
        cell
        for cell in preferred
        if all(
            (cell[0] + dx, cell[1] + dy) in by_xy
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
    }
    target = min(target, len(cells))
    while True:
        xmin, ymin, xmax, ymax = bounds
        width, height = xmax - xmin + 1, ymax - ymin + 1
        needs_width, needs_height = width < minimum[0], height < minimum[1]
        if not needs_width and not needs_height:
            cropped = {
                by_xy[(x, y)]
                for x in range(xmin, xmax + 1)
                for y in range(ymin, ymax + 1)
                if (x, y) in by_xy
            }
            connected = reachable(origin, cropped, geometry.outgoing) & reachable(
                origin, cropped, geometry.incoming
            )
            interior = connected - cardinal_border_cells(connected)
            if (
                len(interior) >= target
                and preferred <= connected
                and padded_preferred <= interior
            ):
                return connected
        choices = []
        for candidate in (
            (xmin - 1, ymin, xmax, ymax),
            (xmin, ymin, xmax + 1, ymax),
            (xmin, ymin - 1, xmax, ymax),
            (xmin, ymin, xmax, ymax + 1),
        ):
            lo_x, lo_y, hi_x, hi_y = candidate
            if (
                lo_x < limits[0]
                or lo_y < limits[1]
                or hi_x > limits[2]
                or hi_y > limits[3]
                or _rectangle_area(candidate) > budget
            ):
                continue
            grows_width = hi_x - lo_x + 1 > width
            if needs_width and not needs_height and not grows_width:
                continue
            if needs_height and not needs_width and grows_width:
                continue
            aspect = abs(
                (hi_x - lo_x + 1) / minimum[0] - (hi_y - lo_y + 1) / minimum[1]
            )
            choices.append((aspect, _rectangle_area(candidate), candidate))
        if not choices:
            return None
        bounds = min(choices)[2]


def compact_encounter(
    data,
    player,
    members,
    cell_budget=None,
    *,
    minimum_cells=25,
    minimum_dimensions=(5, 5),
    spread_opponents=False,
    automatic_cell_budget=MAX_CELL_BUDGET,
    dimensions_include_border=False,
):
    """Local encounter formation on one mutually reachable native component.

    Automatic selection preserves feasible original monster positions and
    leaves maneuvering space beyond both placement teams. Native rectangular
    crops are preferred, with a bounded BFS fallback for irregular terrain.
    Smaller native components remain usable. Directed edges, native heights,
    and ambiguous-column removal remain authoritative.
    """
    if type(minimum_cells) is not int or not 25 <= minimum_cells <= MAX_CELL_BUDGET:
        raise ValueError("Automatic encounter minimum exceeds the cell budget")
    if type(spread_opponents) is not bool:
        raise ValueError("Invalid opposing formation spread policy")
    if type(dimensions_include_border) is not bool:
        raise ValueError("Invalid arena rectangle dimension policy")
    if (
        not isinstance(minimum_dimensions, (tuple, list))
        or len(minimum_dimensions) != 2
        or any(
            type(value) is not int or not 5 <= value <= 50
            for value in minimum_dimensions
        )
    ):
        raise ValueError("Automatic encounter dimensions must be between 5 and 50")
    automatic_size = cell_budget is None
    if automatic_size:
        cell_budget = automatic_cell_budget

    origin = _cell(player)
    originals = [_cell(member) for member in members]
    if not originals or len(originals) > 126:
        raise ValueError("Invalid encounter monster count")
    if type(cell_budget) is not int or not 2 <= cell_budget <= MAX_CELL_BUDGET:
        raise ValueError(
            "Encounter cell budget must be between2 and " + str(MAX_CELL_BUDGET)
        )
    geometry = prepare_geometry(data)
    memoize = isinstance(data, PreparedGeometry)
    key = (
        id(geometry),
        origin,
        tuple(originals),
        cell_budget,
        automatic_size,
        minimum_cells,
        tuple(minimum_dimensions),
        spread_opponents,
        dimensions_include_border,
    )
    if memoize:
        with _compact_encounters_lock:
            cached = _compact_encounters.get(key)
            if cached is not None and cached[0] is geometry:
                _compact_encounters.move_to_end(key)
                return _thaw_compact_encounter(cached[1])
    result = _select_compact_encounter(
        geometry,
        origin,
        originals,
        cell_budget,
        automatic_size,
        minimum_cells,
        minimum_dimensions,
        spread_opponents,
        memoize,
        dimensions_include_border,
    )
    if memoize:
        frozen = _freeze_compact_encounter(result)
        with _compact_encounters_lock:
            _compact_encounters[key] = (geometry, frozen)
            _compact_encounters.move_to_end(key)
            while len(_compact_encounters) > _COMPACT_ENCOUNTER_LIMIT:
                _compact_encounters.popitem(last=False)
        return _thaw_compact_encounter(frozen)
    return result


# Retain geometry identity with each entry; cached results contain only immutable
# values. Map IDs alone cannot distinguish native exports or revised topology.
_COMPACT_ENCOUNTER_LIMIT = 32
_compact_encounters = OrderedDict()
_compact_encounters_lock = RLock()


def _freeze_compact_encounter(result):
    return (
        result["map_id"],
        frozenset(result["cells"]),
        frozenset(result["edges"]),
        tuple(result["placement"][0]),
        tuple(result["placement"][1]),
        tuple(result["participant_positions"]),
        frozenset(result["blocked_ambiguous"]),
        result["bounds"],
    )


def _thaw_compact_encounter(result):
    return dict(
        map_id=result[0],
        cells=set(result[1]),
        edges=set(result[2]),
        placement={0: list(result[3]), 1: list(result[4])},
        participant_positions=list(result[5]),
        blocked_ambiguous=set(result[6]),
        bounds=result[7],
    )


def _select_compact_encounter(
    geometry,
    origin,
    originals,
    cell_budget,
    automatic_size,
    minimum_cells,
    minimum_dimensions,
    spread_opponents,
    memoize,
    dimensions_include_border,
):
    selected, ambiguous = encounter_component(geometry, origin, memoize=memoize)
    component = selected
    # Relocated opponents belong to the local encounter, not their former
    # world positions. Keeping those positions can force a long native detour
    # around walls or bridges and split the visible fight into distant wings.
    preferred = (
        {origin}
        if automatic_size and spread_opponents
        else _preferred_originals(origin, originals, selected, cell_budget)
    )
    target_cells = max(
        minimum_cells,
        (1 + max(12, len(originals)) + 12)
        if dimensions_include_border
        else (12 + max(12, len(originals)) + 12),
    )
    rectangle = None
    if automatic_size:
        rectangle = _rectangular_encounter(
            origin,
            preferred,
            selected,
            geometry,
            minimum_dimensions,
            target_cells,
            cell_budget,
        )
    # A narrow native walkway may only offer interior capacity after a long
    # detour into another region. Prefer the local connected fallback rather
    # than inflating a small encounter beyond twice its playable target.
    if spread_opponents and rectangle is not None and len(rectangle) > 2 * target_cells:
        rectangle = None
    # The requested map budget includes blocked rectangle holes, not only
    # playable cells. Both the selected count and rectangle are capped.
    # Narrow native corridors remain valid without invented floor cells.
    bounded = rectangle if rectangle is not None else {origin}
    queue = deque() if rectangle is not None else deque([origin])
    xmin = xmax = origin[0]
    ymin = ymax = origin[1]
    best_fallback = None
    while queue and len(bounded) < cell_budget:
        current = queue.popleft()
        for target in geometry.outgoing.get(current, ()):
            if target not in selected:
                continue
            if target in bounded:
                continue
            lo_x, hi_x = min(xmin, target[0]), max(xmax, target[0])
            lo_y, hi_y = min(ymin, target[1]), max(ymax, target[1])
            if (hi_x - lo_x + 1) * (hi_y - lo_y + 1) > cell_budget:
                continue
            bounded.add(target)
            queue.append(target)
            xmin, xmax, ymin, ymax = lo_x, hi_x, lo_y, hi_y
            if automatic_size and len(bounded) >= target_cells:
                connected = reachable(origin, bounded, geometry.outgoing) & reachable(
                    origin, bounded, geometry.incoming
                )
                if len(connected) >= target_cells and preferred <= connected:
                    bounded = connected
                    queue.clear()
                    break
                if len(connected) >= target_cells and (
                    best_fallback is None
                    or len(preferred & connected) > len(preferred & best_fallback)
                ):
                    best_fallback = connected
            if len(bounded) == cell_budget:
                break
    selected = reachable(origin, bounded, geometry.outgoing) & reachable(
        origin, bounded, geometry.incoming
    )
    if automatic_size and not preferred <= selected and best_fallback is not None:
        selected = best_fallback
    # A budgeted BFS can stop halfway through a frontier, leaving native floor
    # cells blocked inside the published rectangle. Close the crop over the
    # original unambiguous component without expanding its bounds or budget.
    xmin, ymin, xmax, ymax = _bounds(selected)
    cropped = {
        cell
        for cell in component
        if xmin <= cell[0] <= xmax and ymin <= cell[1] <= ymax
    }
    selected = reachable(origin, cropped, geometry.outgoing) & reachable(
        origin, cropped, geometry.incoming
    )
    if len(selected) <= len(originals):
        raise ValueError(
            "Native reachable encounter component lacks participant capacity"
        )
    distances = {origin: 0}
    pending = deque([origin])
    while pending:
        current = pending.popleft()
        for target in geometry.outgoing.get(current, ()):
            if target not in selected:
                continue
            if target not in distances:
                distances[target] = distances[current] + 1
                pending.append(target)
    free = selected - {origin}
    interior = selected - cardinal_border_cells(selected)
    separation = max(distances.values()) * 0.6
    relocated = []
    for original in originals:
        if original in free and not spread_opponents:
            chosen = original
        else:
            # Spread policy uses the distant native side and distributes NPCs;
            # legacy callers retain their six-step source-near formation.
            chosen = min(
                free & interior or free,
                key=lambda c: (
                    distances[c] < separation if spread_opponents else False,
                    -min(
                        abs(c[0] - previous[0]) + abs(c[1] - previous[1])
                        for previous in relocated
                    )
                    if spread_opponents and relocated
                    else 0,
                    -distances[c] if spread_opponents else abs(distances[c] - 6),
                    abs(c[0] - original[0]) + abs(c[1] - original[1]),
                    c,
                ),
            )
        relocated.append(chosen)
        free.remove(chosen)
    chosen_edges = edges_within(selected, geometry.outgoing)
    return dict(
        map_id=geometry.map_id,
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
