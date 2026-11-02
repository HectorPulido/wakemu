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
    member_radii=None,
    player_radius=0,
    allow_border_footprints=False,
    player_slots=1,
    member_point_cells=None,
    placement_ground_cells=None,
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
    if type(allow_border_footprints) is not bool:
        raise ValueError("Invalid ordinary actor perimeter policy")
    if type(player_slots) is not int or not 1 <= player_slots <= 127:
        raise ValueError("Invalid ordinary party placement capacity")
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
    if player_slots + len(originals) > 127:
        raise ValueError("Ordinary party placement exceeds native actor capacity")
    if type(cell_budget) is not int or not 2 <= cell_budget <= MAX_CELL_BUDGET:
        raise ValueError(
            "Encounter cell budget must be between2 and " + str(MAX_CELL_BUDGET)
        )
    from .combat_placement_footprints import radii_for

    radii = radii_for(originals, member_radii, player_radius)
    geometry = prepare_geometry(data)
    if member_point_cells is not None:
        member_point_cells = frozenset(_cell(cell) for cell in member_point_cells)
    if placement_ground_cells is not None:
        placement_ground_cells = frozenset(
            _cell(cell) for cell in placement_ground_cells
        )
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
        radii,
        player_radius,
        allow_border_footprints,
        player_slots,
        member_point_cells,
        placement_ground_cells,
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
        radii,
        player_radius,
        allow_border_footprints,
        player_slots,
        member_point_cells,
        placement_ground_cells,
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
        tuple(result.get("party_reserved_cells", ())),
    )


def _thaw_compact_encounter(result):
    thawed = dict(
        map_id=result[0],
        cells=set(result[1]),
        edges=set(result[2]),
        placement={0: list(result[3]), 1: list(result[4])},
        participant_positions=list(result[5]),
        blocked_ambiguous=set(result[6]),
        bounds=result[7],
    )
    if result[8]:
        thawed["party_reserved_cells"] = result[8]
    return thawed


class _FormationMobility:
    """Cheap occupancy witnesses for initial placement, not cast/move authority."""

    def __init__(self, cells, outgoing, by_xy):
        self.cells, self.outgoing, self.by_xy = cells, outgoing, by_xy
        self.moves = {}

    def exits(self, center, radius, covered, occupied):
        from .combat_placement_footprints import covered_cells

        key = center, radius
        if key not in self.moves:
            moves = []
            for target in self.outgoing.get(center, ()):
                if target == center or target not in self.cells:
                    continue
                try:
                    destination = covered_cells(
                        target, radius, self.cells, by_xy=self.by_xy
                    )
                except ValueError:
                    continue
                # A move can retain part of its own registered footprint.
                moves.append(destination - covered)
            self.moves[key] = tuple(moves)
        return tuple(move for move in self.moves[key] if move.isdisjoint(occupied))

    def score(self, center, radius, covered, occupied, protected_exits, exit_owners):
        affected = {owner for cell in covered for owner in exit_owners.get(cell, ())}
        newly_trapped = sum(
            all(not move.isdisjoint(covered) for move in protected_exits[owner])
            for owner in affected
        )
        no_exit = not self.exits(center, radius, covered, occupied)
        # Prefer one free cardinal cell between footprints. Further separation
        # has no extra reward, so the existing cohesive formation remains local.
        touching = any(
            self.by_xy.get((cell[0] + dx, cell[1] + dy)) in occupied
            for cell in covered
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
        return newly_trapped, no_exit, touching


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
    member_radii,
    player_radius,
    allow_border_footprints,
    player_slots,
    member_point_cells,
    placement_ground_cells,
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
    target_cells = max(
        target_cells,
        player_slots * (2 * player_radius + 1) ** 2
        + sum((2 * radius + 1) ** 2 for radius in member_radii)
        + 12,
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
    if len(selected) > cell_budget or _rectangle_area(_bounds(selected)) > cell_budget:
        raise ValueError("Native arena crop exceeds configured cell budget")
    if len(selected) <= len(originals):
        raise ValueError(
            "Native reachable encounter component lacks participant capacity"
        )
    return _formation_on_selected(
        geometry,
        origin,
        originals,
        selected,
        ambiguous,
        spread_opponents=spread_opponents,
        member_radii=member_radii,
        player_radius=player_radius,
        allow_border_footprints=allow_border_footprints,
        player_slots=player_slots,
        member_point_cells=member_point_cells,
        placement_ground_cells=placement_ground_cells,
    )


def _formation_on_selected(
    geometry,
    origin,
    originals,
    selected,
    ambiguous,
    *,
    spread_opponents,
    member_radii,
    player_radius,
    allow_border_footprints,
    player_slots,
    member_point_cells,
    reserved_cells=(),
    placement_ground_cells=None,
    fixed_member_positions=None,
):
    """Reuse one native footprint allocator independently of arena cropping."""
    xmin, ymin, xmax, ymax = _bounds(selected)
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
    from .combat_placement_footprints import covered_cells

    by_xy = {cell[:2]: cell for cell in selected}
    if placement_ground_cells is not None:
        ordinary_ground = selected.intersection(placement_ground_cells) - set(
            reserved_cells
        )
        placement_ground_cells = reachable(
            origin, ordinary_ground, geometry.outgoing
        ) & reachable(origin, ordinary_ground, geometry.incoming)
        placement_ground_cells = placement_ground_cells.intersection(ordinary_ground)
    if placement_ground_cells is not None and origin not in placement_ground_cells:
        raise ValueError("Admission player is outside qualified ordinary ground")
    player_covered = covered_cells(origin, player_radius, selected, by_xy=by_xy)
    party_positions = [origin]
    reserved = set(reserved_cells)
    fixed = {} if fixed_member_positions is None else dict(fixed_member_positions)
    fixed_bodies = {}
    fixed_occupied = set()
    for index, center in fixed.items():
        # Reviewed fixed constructors use native terrain; the renderable-ground
        # restriction belongs to ordinary formation and player walking.
        if (
            type(index) is not int
            or not 0 <= index < len(originals)
            or center not in selected
            or member_radii[index] == 0
            and member_point_cells is not None
            and center not in member_point_cells
        ):
            raise ValueError("Fixed initial actor is outside qualified native terrain")
        body = covered_cells(center, member_radii[index], selected, by_xy=by_xy)
        if body & (reserved | fixed_occupied):
            raise ValueError("Fixed initial actor footprints overlap")
        fixed_bodies[index] = body
        fixed_occupied.update(body)
    if player_covered & (reserved | fixed_occupied):
        raise ValueError("Admission player overlaps an authored initial obstacle")
    occupied = set(player_covered) | reserved | fixed_occupied
    placed = [(origin, player_radius, player_covered)] + [
        (center, member_radii[index], fixed_bodies[index])
        for index, center in fixed.items()
    ]
    for center in sorted(selected, key=lambda cell: (distances[cell], cell)):
        if placement_ground_cells is not None and center not in placement_ground_cells:
            continue
        if len(party_positions) == player_slots:
            break
        try:
            covered = covered_cells(center, player_radius, selected, by_xy=by_xy)
        except ValueError:
            continue
        if covered & occupied:
            continue
        party_positions.append(center)
        occupied.update(covered)
        placed.append((center, player_radius, covered))
    if len(party_positions) != player_slots:
        raise ValueError("Native arena lacks disjoint party placement capacity")
    free = selected - occupied
    mobility = _FormationMobility(selected, geometry.outgoing, by_xy)
    interior = selected - cardinal_border_cells(selected)
    # Scale separation to the selected rectangle, not a folded native detour.
    # Existing arena side policy (normally 7--20) still controls encounter size.
    separation = max(xmax - xmin + 1, ymax - ymin + 1) * 0.6
    relocated = [None] * len(originals)
    for index, center in fixed.items():
        relocated[index] = center
    formation_distances = None
    # Pack larger native footprints first, without changing roster output order.
    for index in sorted(range(len(originals)), key=lambda i: (-member_radii[i], i)):
        if index in fixed:
            continue
        original, radius = originals[index], member_radii[index]
        candidates = set()
        footprints = {}
        for center in free:
            if (
                placement_ground_cells is not None
                and center not in placement_ground_cells
            ):
                continue
            if (
                radius == 0
                and member_point_cells is not None
                and center not in member_point_cells
            ):
                continue
            try:
                covered = covered_cells(center, radius, selected, by_xy=by_xy)
            except ValueError:
                continue
            if covered <= free and (
                radius == 0 or covered <= interior or allow_border_footprints
            ):
                candidates.add(center)
                footprints[center] = covered
        if not candidates:
            raise ValueError(
                "Native arena lacks disjoint ordinary actor footprint capacity"
            )
        if original in candidates and not spread_opponents:
            chosen = original
        elif spread_opponents:
            # Compare against each actor's currently available exits, so an
            # already blocked actor is not counted as newly trapped. Include
            # the player footprint and retain the complete native edge graph.
            protected_exits = [
                mobility.exits(center, size, covered, occupied)
                for center, size, covered in placed
            ]
            # Only an actor with an exit intersecting the candidate body can
            # lose mobility. Keep max-roster scoring local to those footprints.
            exit_owners = defaultdict(set)
            for owner, exits in enumerate(protected_exits):
                for move in exits:
                    for cell in move:
                        exit_owners[cell].add(owner)
            chosen = min(
                candidates,
                key=lambda c: (
                    *mobility.score(
                        c, radius, footprints[c], occupied, protected_exits, exit_owners
                    ),
                    c not in interior,
                    formation_distances.get(c, len(selected))
                    if formation_distances is not None
                    else abs(distances[c] - separation),
                    abs(c[0] - original[0]) + abs(c[1] - original[1]),
                    c,
                ),
            )
        else:
            # Separate the teams, then grow one cohesive native formation.
            # Screen-space spacing must not scatter NPCs along a folded ramp.
            chosen = min(
                candidates & interior or candidates,
                key=lambda c: (
                    formation_distances.get(c, len(selected))
                    if spread_opponents and formation_distances is not None
                    else abs(distances[c] - separation)
                    if spread_opponents
                    else abs(distances[c] - 6),
                    abs(c[0] - original[0]) + abs(c[1] - original[1]),
                    c,
                ),
            )
        relocated[index] = chosen
        free.difference_update(footprints[chosen])
        occupied.update(footprints[chosen])
        placed.append((chosen, radius, footprints[chosen]))
        if spread_opponents and formation_distances is None:
            formation_distances = {chosen: 0}
            pending = deque([chosen])
            while pending:
                current = pending.popleft()
                for target in geometry.outgoing.get(current, ()):
                    if target in selected and target not in formation_distances:
                        formation_distances[target] = formation_distances[current] + 1
                        pending.append(target)
    chosen_edges = edges_within(selected, geometry.outgoing)
    result = dict(
        map_id=geometry.map_id,
        cells=selected,
        edges=chosen_edges,
        placement={0: party_positions, 1: relocated},
        participant_positions=list(zip(originals, relocated)),
        blocked_ambiguous=ambiguous,
        bounds=(
            min(c[0] for c in selected),
            min(c[1] for c in selected),
            max(c[0] for c in selected),
            max(c[1] for c in selected),
        ),
    )
    if player_slots > 1:
        result["party_reserved_cells"] = tuple(party_positions)
    return result


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


def full_room_encounter(
    data,
    player,
    members,
    *,
    member_radii=None,
    player_radius=0,
    player_slots=6,
    member_point_cells=None,
    reserved_cells=(),
    placement_ground_cells=None,
    fixed_member_positions=None,
):
    """Place ordinary bodies legally while retaining every declared room cell."""
    geometry = prepare_geometry(data)
    origin, originals = _cell(player), tuple(_cell(member) for member in members)
    if (
        origin not in geometry.cells
        or not originals
        or len(originals) > 126
        or len(set(originals)) != len(originals)
        or any(point not in geometry.cells for point in originals)
        or len({cell[:2] for cell in geometry.cells}) != len(geometry.cells)
        or type(player_slots) is not int
        or not 1 <= player_slots <= 127
        or player_slots + len(originals) > 127
    ):
        raise ValueError("Invalid full room participant or native altitude scope")
    if _rectangle_area(_bounds(geometry.cells)) > 32767:
        raise ValueError("Full room rectangle exceeds native wire bounds")
    from .combat_placement_footprints import radii_for

    radii = radii_for(originals, member_radii, player_radius)
    fixed = {} if fixed_member_positions is None else dict(fixed_member_positions)
    if any(
        type(index) is not int or not 0 <= index < len(originals) for index in fixed
    ):
        raise ValueError("Fixed actor placement lacks its original member index")
    fixed = {index: _cell(cell) for index, cell in fixed.items()}
    declared_reserved = frozenset(_cell(cell) for cell in reserved_cells)
    if not declared_reserved.issubset(geometry.cells):
        raise ValueError("Authored initial obstacle leaves the full native room")
    reserved_columns = {cell[:2] for cell in declared_reserved}
    reserved = frozenset(
        cell for cell in geometry.cells if cell[:2] in reserved_columns
    )
    from .combat_placement_footprints import covered_cells

    fixed_covered = set()
    for index, center in fixed.items():
        body = covered_cells(center, radii[index], geometry.cells)
        if body & (reserved | fixed_covered):
            raise ValueError(
                "Fixed actor placement overlaps an initial native obstacle"
            )
        fixed_covered.update(body)
    actor_cells = geometry.cells - reserved
    admission_footprint = covered_cells(origin, player_radius, geometry.cells)
    admission_reserved = reserved | fixed_covered
    blocked_origin = bool(admission_footprint & admission_reserved)
    candidates = [origin]
    if blocked_origin:
        # These are prospective constructor slots, not live world obstacles.
        # Search actual native edges; never invent a floor or movement edge.
        candidates, seen, pending = [], {origin}, deque([origin])
        while pending:
            current = pending.popleft()
            if current in actor_cells and current not in fixed_covered:
                candidates.append(current)
            for target in sorted(geometry.outgoing.get(current, ())):
                if target in geometry.cells and target not in seen:
                    seen.add(target)
                    pending.append(target)
    last_error = None
    for placement_origin in candidates:
        component = reachable(
            placement_origin, actor_cells, geometry.outgoing
        ) & reachable(placement_origin, actor_cells, geometry.incoming)
        try:
            if len(component) <= len(originals):
                raise ValueError("Full room lacks native participant capacity")
            result = _formation_on_selected(
                geometry,
                placement_origin,
                originals,
                component,
                set(),
                spread_opponents=True,
                member_radii=radii,
                player_radius=player_radius,
                allow_border_footprints=True,
                player_slots=player_slots,
                member_point_cells=member_point_cells,
                reserved_cells=reserved,
                placement_ground_cells=placement_ground_cells,
                fixed_member_positions=fixed,
            )
        except ValueError as exc:
            if not blocked_origin:
                raise
            last_error = exc
            continue
        if blocked_origin:
            result["participant_player_position"] = [
                list(origin),
                list(placement_origin),
            ]
            result["native_initial_player_relocation"] = dict(
                schema="wakemu-reserved-slot-placement-v1",
                physical_radius=player_radius,
                reserved_cells=[list(cell) for cell in sorted(admission_reserved)],
            )
        result.update(
            cells=set(geometry.cells),
            edges=set(geometry.edges),
            bounds=_bounds(geometry.cells),
        )
        return result
    raise ValueError(
        "Full room lacks legal placement outside reserved spawn slots"
    ) from last_error
