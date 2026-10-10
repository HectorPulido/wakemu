"""Generate local multi-cell placement zones from native directed terrain.

Six cells per team is an explicit configurable local formation policy, not a
claim about the official server's placement generator. No terrain is invented.
"""
from collections import defaultdict, deque
import hashlib


def _cell(value):
    if (
        not isinstance(value, (tuple, list))
        or len(value) != 3
        or any(type(n) is not int for n in value)
    ):
        raise ValueError("Invalid placement coordinate")
    return tuple(value)


def _distances(seeds, cells, outgoing, blocked):
    distances = {seed: 0 for seed in seeds}
    queue = deque(sorted(seeds))
    while queue:
        origin = queue.popleft()
        for target in sorted(outgoing[origin]):
            if target in cells and target not in blocked and target not in distances:
                distances[target] = distances[origin] + 1
                queue.append(target)
    return distances


def opposing_starts(cells, edges, placement, *, avoid_cells=()):
    """Choose distant combat starts inside two native placement regions."""
    cells = {_cell(cell) for cell in cells}
    avoided = {_cell(cell) for cell in avoid_cells}
    zones = {team: {_cell(cell) for cell in placement[team]} for team in (0, 1)}
    if (
        any(not zone or not zone <= cells for zone in zones.values())
        or zones[0] & zones[1]
    ):
        raise ValueError("Invalid opposing start regions")
    outgoing = defaultdict(set)
    for start, end in edges:
        outgoing[_cell(start)].add(_cell(end))
    preferred = {team: zones[team] - avoided or zones[team] for team in (0, 1)}
    origin = min(preferred[0])
    distances = _distances({origin}, cells, outgoing, set())
    candidates = preferred[1] & distances.keys()
    if not candidates:
        raise ValueError("Opposing placement region is unreachable")
    target = max(candidates, key=lambda cell: (distances[cell], cell))
    distances = _distances({target}, cells, outgoing, set())
    candidates = preferred[0] & distances.keys()
    if not candidates:
        raise ValueError("Opposing placement region has no return path")
    origin = max(candidates, key=lambda cell: (distances[cell], cell))
    return {0: origin, 1: target}


def generate(
    cells,
    edges,
    seeds,
    *,
    slots_per_team=6,
    variation_seed=None,
    avoid_cells=(),
    spread_teams=False,
):
    """Return disjoint team0/1 placement sets containing every current actor.

    Native outgoing paths choose nearby candidates; enemy seed cells are blocked
    during that search. Small maps yield their available capacity, never fake
    slots. More than six actors retain all their occupied seed cells.
    """
    if type(slots_per_team) is not int or not 1 <= slots_per_team <= 127:
        raise ValueError("Invalid local placement capacity")
    if type(spread_teams) is not bool:
        raise ValueError("Invalid team placement spread policy")
    if variation_seed is not None and (
        type(variation_seed) is not int or variation_seed < 0
    ):
        raise ValueError("Invalid placement variation seed")
    cells = {_cell(cell) for cell in cells}
    avoided = {_cell(cell) for cell in avoid_cells}
    if not avoided <= cells:
        raise ValueError("Avoided placement cells are outside selected terrain")
    if not cells or len({cell[:2] for cell in cells}) != len(cells):
        raise ValueError("Placement needs selected unique-height terrain")
    if not isinstance(seeds, dict) or set(seeds) != {0, 1}:
        raise ValueError("Both placement teams require actor seeds")
    selected = {team: {_cell(seed) for seed in group} for team, group in seeds.items()}
    if (
        any(not group or not group <= cells for group in selected.values())
        or selected[0] & selected[1]
        or sum(map(len, selected.values())) > 127
    ):
        raise ValueError("Placement actor seeds overlap or are unavailable")
    outgoing = defaultdict(set)
    for raw in edges:
        if not isinstance(raw, (tuple, list)) or len(raw) != 2:
            raise ValueError("Invalid placement terrain edge")
        origin, target = map(_cell, raw)
        if (
            origin not in cells
            or target not in cells
            or abs(origin[0] - target[0]) + abs(origin[1] - target[1]) != 1
        ):
            raise ValueError("Placement edge is outside native selected terrain")
        outgoing[origin].add(target)
    distances = {
        team: _distances(selected[team], cells, outgoing, selected[1 - team])
        for team in (0, 1)
    }
    anchor_distances = None
    if spread_teams:
        # Select opposite native reachable ends, then grow each formation around
        # its own end. Actor seeds remain selectable even when adjacent.
        available = {
            team: set(distances[team]) - selected[1 - team] - avoided for team in (0, 1)
        }
        if all(available.values()):
            enemy_distances = _distances(selected[1], cells, outgoing, set())
            anchor0 = max(available[0], key=lambda c: (enemy_distances.get(c, -1), c))
            from_anchor0 = _distances({anchor0}, cells, outgoing, set())
            anchor1 = max(available[1], key=lambda c: (from_anchor0.get(c, -1), c))
            anchor_distances = {
                0: _distances({anchor0}, cells, outgoing, selected[1]),
                1: _distances({anchor1}, cells, outgoing, selected[0]),
            }

    def candidate_order(team, cell):
        distance = (
            anchor_distances[team].get(cell, len(cells))
            if anchor_distances is not None
            else distances[team][cell]
        )
        if variation_seed is None:
            return (cell in avoided, distance, cell)
        # Keep native distance priority; vary only equally reachable cells.
        # A durable encounter seed makes retries independent of input order.
        tie = hashlib.sha256(
            repr((variation_seed, team, cell)).encode("ascii")
        ).digest()
        return (cell in avoided, distance, tie, cell)

    candidates = {
        team: deque(sorted(distances[team], key=lambda c: candidate_order(team, c)))
        for team in (0, 1)
    }
    occupied = selected[0] | selected[1]
    limits = {team: max(slots_per_team, len(selected[team])) for team in (0, 1)}
    while True:
        added = False
        for team in (0, 1):
            if len(selected[team]) >= limits[team]:
                continue
            while candidates[team] and candidates[team][0] in occupied:
                candidates[team].popleft()
            if candidates[team]:
                if anchor_distances is not None:
                    available = set(candidates[team]) - occupied
                    if not available:
                        candidates[team].clear()
                        continue

                    # Spatial spacing only ranks already native-reachable
                    # candidates; it never creates a path or terrain cell.
                    def spread_order(cell):
                        own = anchor_distances[team].get(cell, len(cells))
                        opposing = anchor_distances[1 - team].get(cell, len(cells))
                        spacing = min(
                            abs(cell[0] - chosen[0]) + abs(cell[1] - chosen[1])
                            for chosen in selected[team]
                        )
                        return (
                            cell in avoided,
                            own > opposing,
                            -spacing,
                            candidate_order(team, cell),
                        )

                    cell = min(available, key=spread_order)
                    candidates[team].remove(cell)
                else:
                    cell = candidates[team].popleft()
                selected[team].add(cell)
                occupied.add(cell)
                added = True
        if not added:
            break
    return selected
