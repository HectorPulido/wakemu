"""Declared zone-wide resource placement on reachable original native terrain.

Player positions choose reachable components only. They never rank spawn
locations. Event-seeded spatial buckets spread resources through the original
region; reserved native approach paths and spacing prevent a dense wall of
plants. Capacity shortfalls cap the population instead of filling adjacent tiles.
"""
from collections import defaultdict, deque
from hashlib import sha256
from math import isqrt

POLICY = "wakemu.environmental-resource-reachable-zone-spread.v2"


def _point(value):
    point = tuple(value)
    if len(point) != 3 or any(type(axis) is not int for axis in point):
        raise ValueError("Invalid original resource terrain point")
    return point


def _rank(seed, value):
    return sha256((seed + ":" + repr(value)).encode()).digest()


def spread_order(points, *, seed, quantity):
    """Return a stable, shuffled round-robin over spatial bins of the zone."""
    if type(seed) is not str or not seed or type(quantity) is not int or quantity < 1:
        raise ValueError("Invalid environmental resource spread identity")
    points = tuple(sorted({_point(point) for point in points}))
    if not points:
        return ()
    side = isqrt(quantity - 1) + 1
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    buckets = defaultdict(list)
    for point in points:
        bucket = (
            (point[0] - min_x) * side // (max_x - min_x + 1),
            (point[1] - min_y) * side // (max_y - min_y + 1),
        )
        buckets[bucket].append(point)
    active = deque(
        deque(sorted(buckets[key], key=lambda point: _rank(seed, point)))
        for key in sorted(buckets, key=lambda key: _rank(seed, ("bucket", key)))
    )
    result = []
    while active:
        bucket = active.popleft()
        result.append(bucket.popleft())
        if bucket:
            active.append(bucket)
    return tuple(result)


def plan(
    native_surfaces, geometry, *, region_id, origins, taken, quantity, seed, reserve=32
):
    """Plan native points plus approach proofs; do not mutate a DB or World.

    ``native_surfaces`` has the planting_cells.cells mapping shape. Reachability
    uses the complete map so a path may pass through another territory, while
    every resource remains strictly inside the original declared region. All
    selected XYZs and each approach edge exist in both directions natively.
    """
    if (
        type(region_id) is not int
        or region_id <= 0
        or type(quantity) is not int
        or not 1 <= quantity <= 4096
        or type(reserve) is not int
        or not 0 <= reserve <= 4096
    ):
        raise ValueError("Invalid environmental resource placement bounds")
    blocked = set()
    for point in taken:
        if len(point) != 2 or any(type(axis) is not int for axis in point):
            raise ValueError("Invalid resource occupied XY")
        blocked.add(tuple(point))
    floor = {_point(point) for point in geometry["cells"]}
    edges = {(_point(start), _point(end)) for start, end in geometry["edges"]}
    adjacency = {point: [] for point in floor}
    for start, end in edges:
        if start in floor and end in floor and (end, start) in edges:
            adjacency[start].append(end)
    for neighbors in adjacency.values():
        neighbors.sort()
    roots = sorted({_point(point) for point in origins}.intersection(floor))
    if not roots:
        return ()
    parent = dict.fromkeys(roots)
    depth = dict.fromkeys(roots, 0)
    queue = deque(roots)
    while queue:
        point = queue.popleft()
        for neighbor in adjacency[point]:
            if neighbor not in parent and neighbor[:2] not in blocked:
                parent[neighbor] = point
                depth[neighbor] = depth[point] + 1
                queue.append(neighbor)
    original = {
        (x, y, row["z"])
        for (x, y), rows in native_surfaces.items()
        for row in rows
        if row["region_id"] == region_id
    }
    original = {_point(point) for point in original}
    ordinals = {point: ordinal for ordinal, point in enumerate(sorted(original))}
    candidates = (
        point
        for point in original.intersection(parent)
        if point[:2] not in blocked and point not in roots and adjacency[point]
    )
    selected, selected_xy, spaced, transit = [], set(), set(), set()
    for point in spread_order(candidates, seed=seed, quantity=quantity):
        xy = point[:2]
        if xy in spaced or xy in transit:
            continue
        approach, path = None, None
        for neighbor in sorted(
            adjacency[point], key=lambda p: (depth.get(p, len(floor)), p)
        ):
            if neighbor not in parent:
                continue
            route, current = [], neighbor
            while current is not None:
                route.append(current)
                current = parent[current]
            if any(cell[:2] == xy or cell[:2] in selected_xy for cell in route):
                continue
            approach, path = neighbor, tuple(reversed(route))
            break
        if approach is None:
            continue
        selected.append(
            dict(
                x=point[0],
                y=point[1],
                z=point[2],
                ordinal=ordinals[point],
                approach=approach,
                path=path,
                placement_policy=POLICY,
            )
        )
        selected_xy.add(xy)
        # L1 >= 3 leaves an empty tile between neighboring resource anchors.
        spaced.update(
            (point[0] + dx, point[1] + dy)
            for dx in range(-2, 3)
            for dy in range(-2, 3)
            if abs(dx) + abs(dy) < 3
        )
        transit.update(cell[:2] for cell in path)
        if len(selected) == quantity + reserve:
            break
    return tuple(selected)
