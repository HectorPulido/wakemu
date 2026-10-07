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


def generate(cells, edges, seeds, *, slots_per_team=6, variation_seed=None):
    """Return disjoint team0/1 placement sets containing every current actor.

    Native outgoing paths choose nearby candidates; enemy seed cells are blocked
    during that search. Small maps yield their available capacity, never fake
    slots. More than six actors retain all their occupied seed cells.
    """
    if type(slots_per_team) is not int or not 1 <= slots_per_team <= 127:
        raise ValueError("Invalid local placement capacity")
    if variation_seed is not None and (
        type(variation_seed) is not int or variation_seed < 0
    ):
        raise ValueError("Invalid placement variation seed")
    cells = {_cell(cell) for cell in cells}
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

    def candidate_order(team, cell):
        if variation_seed is None:
            return (distances[team][cell], cell)
        # Keep native distance priority; vary only equally reachable cells.
        # A durable encounter seed makes retries independent of input order.
        tie = hashlib.sha256(
            repr((variation_seed, team, cell)).encode("ascii")
        ).digest()
        return (distances[team][cell], tie, cell)

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
                cell = candidates[team].popleft()
                selected[team].add(cell)
                occupied.add(cell)
                added = True
        if not added:
            break
    return selected
