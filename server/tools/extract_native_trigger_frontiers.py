"""Prove an ordered victory frontier from literal native PositionTrigger cuts.

Pure offline helper. It never creates walking edges, moves trigger positions or
claims to implement the native trigger scripts. Connected parallel trigger
cells form one cut and must close together.
"""
from collections import defaultdict, deque
import math


def _reachable(edges, start, blocked):
    start = tuple(start)
    blocked = set(blocked)
    if start in blocked:
        return set()
    graph = defaultdict(set)
    for a, b in edges:
        a, b = tuple(a), tuple(b)
        if a not in blocked and b not in blocked:
            graph[a].add(b)
    seen = {start}
    queue = deque([start])
    while queue:
        for target in graph[queue.popleft()]:
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def extract(
    geometry, triggers, entry, exit_position, *, blocked_cells=(), expected_rooms=None
):
    """Require a unique linear cut chain and native directed unlock witnesses."""
    from extract_dungeon_topology import components

    cells = set(map(tuple, geometry["cells"]))
    entry = tuple(entry)
    exit_position = tuple(exit_position)
    blocked = set(map(tuple, blocked_cells))
    adjacency = defaultdict(set)
    for a, b in geometry["edges"]:
        a, b = tuple(a), tuple(b)
        if a not in cells or b not in cells:
            raise ValueError("Native edge endpoint is outside native walk cells")
        adjacency[a].add(b)
        adjacency[b].add(a)
    by_position = {}
    identities = set()
    for trigger in triggers:
        if (
            trigger.get("type") != "PositionTrigger"
            or trigger.get("map_id") != geometry["map_id"]
            or type(trigger.get("id")) is not int
            or trigger["id"] <= 0
            or trigger["id"] in identities
        ):
            raise ValueError(
                "Native trigger identity/type/map is invalid or duplicated"
            )
        raw = tuple(trigger.get(k) for k in ("x", "y", "z"))
        if any(
            type(v) not in (int, float) or not math.isfinite(v) or int(v) != v
            for v in raw
        ):
            raise ValueError("Native trigger position must be exactly integral")
        position = tuple(map(int, raw))
        if position not in cells or position in blocked:
            raise ValueError("Native trigger is not a distinct walkable cut cell")
        if position in by_position:
            raise ValueError("Native trigger cut position is duplicated")
        by_position[position] = trigger["id"]
        identities.add(trigger["id"])
    if not by_position:
        raise ValueError("No native trigger frontier candidates")
    cut_positions = set(by_position)
    if (
        entry not in cells
        or exit_position not in cells
        or entry in cut_positions | blocked
        or exit_position in cut_positions | blocked
    ):
        raise ValueError("Native entry/exit is not outside the trigger cuts")
    labels, sizes = components(cells - cut_positions - blocked, adjacency)
    pending = set(cut_positions)
    groups = []
    while pending:
        first = min(pending)
        group = {first}
        queue = deque([first])
        pending.remove(first)
        while queue:
            for neighbor in adjacency[queue.popleft()] & pending:
                group.add(neighbor)
                pending.remove(neighbor)
                queue.append(neighbor)
        neighboring = {labels[q] for p in group for q in adjacency[p] if q in labels}
        if len(neighboring) != 2:
            raise ValueError(
                "Native trigger cut has ambiguous region adjacency or does not separate terrain"
            )
        groups.append(
            dict(
                positions=[list(p) for p in sorted(group)],
                source_ids=[by_position[p] for p in sorted(group)],
                regions=sorted(neighboring),
            )
        )
    # Parallel lanes need not touch each other. Cuts separating the same exact
    # pair of closed native regions belong to one mandatory frontier.
    grouped = {}
    for group in groups:
        key = tuple(group["regions"])
        merged = grouped.setdefault(
            key, dict(regions=group["regions"], positions=[], source_ids=[])
        )
        merged["positions"].extend(group["positions"])
        merged["source_ids"].extend(group["source_ids"])
    groups = list(grouped.values())
    start = labels[entry]
    final = labels[exit_position]
    region_graph = defaultdict(list)
    for index, group in enumerate(groups):
        a, b = group["regions"]
        region_graph[a].append((b, index))
        region_graph[b].append((a, index))
    if start == final:
        raise ValueError("Native trigger candidates do not separate entry from exit")
    if (
        len(region_graph[start]) != 1
        or len(region_graph[final]) != 1
        or any(
            len(neighbors) != 2
            for region, neighbors in region_graph.items()
            if region not in (start, final)
        )
    ):
        raise ValueError("Native trigger frontier graph is branched or cyclic")
    regions = [start]
    ordered = []
    used = set()
    while regions[-1] != final:
        choices = [(r, i) for r, i in region_graph[regions[-1]] if i not in used]
        if len(choices) != 1:
            raise ValueError("Native trigger order is ambiguous or cyclic")
        region, index = choices[0]
        if region in regions:
            raise ValueError("Native trigger order contains a cycle")
        ordered.append(groups[index])
        used.add(index)
        regions.append(region)
    if len(used) != len(groups):
        raise ValueError(
            "Native trigger cuts include an unrelated or cyclic frontier component"
        )
    if expected_rooms is not None and len(regions) != expected_rooms:
        raise ValueError("Native trigger count contradicts required encounter count")
    stages = []
    all_trigger_positions = {tuple(p) for g in ordered for p in g["positions"]}
    for order, region in enumerate(regions, 1):
        later = {tuple(p) for g in ordered[order - 1 :] for p in g["positions"]}
        reachable = _reachable(geometry["edges"], entry, blocked | later)
        region_cells = {p for p, label in labels.items() if label == region}
        if not (region_cells & reachable):
            raise ValueError(
                "Native directed walk cannot enter the unlocked trigger stage"
            )
        if any(labels[p] in regions[order:] for p in reachable if p in labels):
            raise ValueError(
                "Native directed walk bypasses a closed parallel trigger cut"
            )
        stages.append(
            dict(
                order=order,
                region=region,
                cells=[list(p) for p in sorted(region_cells)],
                reachable_cells=len(region_cells & reachable),
                native_cell_count=sizes[region],
            )
        )
    if exit_position not in _reachable(geometry["edges"], entry, blocked):
        raise ValueError(
            "Native directed walking cannot reach the completed exterior approach"
        )
    return dict(
        map_id=geometry["map_id"],
        entry=list(entry),
        exit_position=list(exit_position),
        regions=regions,
        rooms=stages,
        frontiers=[
            dict(group, source_room=i + 1, destination_room=i + 2)
            for i, group in enumerate(ordered)
        ],
        authority="Literal walkable native PositionTrigger cut cells; unique linear native region graph; directed unlock witnesses; no invented walking edges",
    )
