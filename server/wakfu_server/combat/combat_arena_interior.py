"""Reserve native corridors before generating optional arena border hazards."""
from collections import defaultdict
import heapq


def safe_interior(
    cells, edges, seeds, perimeter, *, placement_capacity=0, reserved_cells=()
):
    """Return a mutually reachable placement interior and optional borders.

    Borders are nonblocking native hazards, not walls. The local generator must
    not force participants through its newly generated hazards to meet. Keep
    existing interior routes first; reserve native perimeter cells only where a
    required seed otherwise has no safe route. Never add a terrain edge.
    """
    if type(placement_capacity) is not int or not 0 <= placement_capacity <= 254:
        raise ValueError("Invalid arena interior placement capacity")
    cells = frozenset(map(tuple, cells))
    perimeter = frozenset(map(tuple, perimeter))
    required = frozenset(tuple(cell) for team in seeds.values() for cell in team)
    required |= frozenset(map(tuple, reserved_cells))
    if not required or not required <= cells or not perimeter <= cells:
        raise ValueError("Invalid native arena interior scope")
    outgoing = defaultdict(set)
    incoming = defaultdict(set)
    for raw_start, raw_end in edges:
        start, end = tuple(raw_start), tuple(raw_end)
        if start not in cells or end not in cells:
            raise ValueError("Arena interior edge is outside native terrain")
        outgoing[start].add(end)
        incoming[end].add(start)
    borders = set(perimeter - required)
    origin = min(tuple(cell) for cell in seeds[0])

    def reserve_path(start, destination):
        # Lexicographic cost preserves hazard-free paths even when they are
        # longer. Secondary native step distance bounds unnecessary detours.
        queue = [(0, 0, start)]
        costs = {start: (0, 0)}
        previous = {start: None}
        while queue:
            hazards, steps, current = heapq.heappop(queue)
            if costs[current] != (hazards, steps):
                continue
            if current == destination:
                while current is not None:
                    borders.discard(current)
                    current = previous[current]
                return
            for target in sorted(outgoing[current]):
                cost = (hazards + (target in borders), steps + 1)
                if target not in costs or cost < costs[target]:
                    costs[target] = cost
                    previous[target] = current
                    heapq.heappush(queue, (*cost, target))
        raise ValueError("Combat formation has no mutual native interior corridor")

    for destination in sorted(required):
        reserve_path(origin, destination)
        reserve_path(destination, origin)

    def reachable(graph, excluded):
        found = {origin}
        pending = [origin]
        while pending:
            for target in graph[pending.pop()]:
                if target not in excluded and target not in found:
                    found.add(target)
                    pending.append(target)
        return found

    def connected_interior():
        return frozenset(reachable(outgoing, borders) & reachable(incoming, borders))

    interior = connected_interior()
    if not required <= interior:
        raise ValueError("Combat formation is outside its native interior corridor")
    # Narrow maps previously offered border cells as legal placement capacity.
    # Keep that capacity by reserving native cells, rather than drawing optional
    # hazards beneath placements or shrinking ordinary twelve-slot formations.
    component = reachable(outgoing, set()) & reachable(incoming, set())
    capacity = min(len(component), max(len(required), placement_capacity))
    distances = {origin: 0}
    pending = [origin]
    for current in pending:
        for target in sorted(outgoing[current]):
            if target in component and target not in distances:
                distances[target] = distances[current] + 1
                pending.append(target)
    while len(interior) < capacity:
        destination = min(component - interior, key=lambda c: (distances[c], c))
        reserve_path(origin, destination)
        reserve_path(destination, origin)
        interior = connected_interior()
    return interior, frozenset(borders)
