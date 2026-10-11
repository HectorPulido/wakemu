"""Derive local combat stages from mandatory native gates, retaining annex terrain."""
from collections import defaultdict, deque
import copy
from extract_dungeon_topology import analyze, components
from extract_native_door_flow import shortest_path


def reachable(edges, start, blocked=()):
    adjacency = defaultdict(list)
    blocked = set(map(tuple, blocked))
    for a, b in edges:
        adjacency[tuple(a)].append(tuple(b))
    seen = {tuple(start)} if tuple(start) not in blocked else set()
    queue = deque(seen)
    while queue:
        for target in adjacency[queue.popleft()]:
            if target not in blocked and target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def build(geometry, doors, entry, exit_position):
    """Use only entry-to-exit bridge gates; annex gates share their proven stage."""
    entry, exit_position = tuple(entry), tuple(exit_position)
    cells = set(map(tuple, geometry["cells"]))
    positions = {d["id"]: tuple(d[k] for k in ("x", "y", "z")) for d in doors}
    adjacency = defaultdict(set)
    for a, b in geometry["edges"]:
        a, b = tuple(a), tuple(b)
        adjacency[a].add(b)
        adjacency[b].add(a)
    labels, _ = components(cells - set(positions.values()), adjacency)
    if entry not in labels or exit_position not in labels:
        raise ValueError(
            "Native entry or literal exterior exit is outside a closed region"
        )
    evidence = analyze(geometry, doors, [entry])
    graph = defaultdict(list)
    for door in evidence["doors"]:
        neighbors = door["adjacent_closed_regions"]
        if len(neighbors) > 2:
            raise ValueError("Native gate footprint touches more than two regions")
        if len(neighbors) == 2:
            a, b = neighbors
            graph[a].append((b, door["object_id"]))
            graph[b].append((a, door["object_id"]))

    def regions(start, blocked=None):
        seen, queue = {start}, [start]
        for current in queue:
            for target, gate in graph[current]:
                if gate not in (blocked or set()) and target not in seen:
                    seen.add(target)
                    queue.append(target)
        return seen

    start, end = labels[entry], labels[exit_position]
    if end not in regions(start):
        raise ValueError("No native closed-region route to literal exterior exit")
    bundles = defaultdict(set)
    for region, links in graph.items():
        for other, gate in links:
            bundles[tuple(sorted((region, other)))].add(gate)
    mandatory = []
    for gates in bundles.values():
        before = regions(start, gates)
        if end not in before:
            mandatory.append((len(before), tuple(sorted(gates)), before))
    mandatory.sort()
    if not mandatory:
        raise ValueError("No mandatory native gate separates entry from exterior exit")
    stage_for = {
        region: 1 + sum(region not in before for _, _, before in mandatory)
        for region in set(labels.values())
    }
    physical = []
    for door in evidence["doors"]:
        stages = {stage_for[r] for r in door["adjacent_closed_regions"]}
        if not stages:
            stages = {1}
        if max(stages) - min(stages) > 1:
            raise ValueError("Native gate would skip a combat stage")
        physical.append(
            dict(
                source_id=door["object_id"],
                position=list(door["position"]),
                source_room=min(stages),
                destination_room=max(stages),
                local_annex_gate=len(stages) == 1,
            )
        )
    room_cells = {
        stage: sorted(c for c, region in labels.items() if stage_for[region] == stage)
        for stage in range(1, len(mandatory) + 2)
    }
    rooms = []
    for stage, selected in room_cells.items():
        blocked = [d["position"] for d in physical if d["destination_room"] > stage]
        reached = reachable(geometry["edges"], entry, blocked)
        future = {
            c for later, group in room_cells.items() if later > stage for c in group
        }
        if reached & future:
            raise ValueError("Native directed path bypasses a locked future encounter")
        available = set(selected) & reached
        if not available:
            raise ValueError("Combat stage has no directed-reachable native cell")
        sx, sy = sum(c[0] for c in available), sum(c[1] for c in available)
        size = len(available)
        anchor = min(
            available,
            key=lambda c: ((c[0] * size - sx) ** 2 + (c[1] * size - sy) ** 2, c),
        )
        rooms.append(
            dict(order=stage, anchor=list(anchor), cells=[list(c) for c in selected])
        )
    if exit_position not in reachable(geometry["edges"], entry):
        raise ValueError(
            "Native exterior exit is not directed-reachable with all gates open"
        )
    from wakfu_server.dungeon_physical_doors import POLICY

    return dict(
        asset_map_id=geometry["map_id"],
        policy=POLICY,
        official_room_order_verified=False,
        progression_authority="Explicit local mandatory native gate stages; annex regions share their gate-separated combat stage; all terrain and native gates retained",
        rooms=rooms,
        doors=[],
        physical_doors=physical,
        physical_exit_objects=[],
        exploration_geometry=copy.deepcopy(geometry),
        local_mainspine_evidence=dict(
            entry=list(entry),
            exit=list(exit_position),
            mandatory_gate_ids=[gates[0] for _, gates, _ in mandatory],
            mandatory_gate_groups=[list(gates) for _, gates, _ in mandatory],
            retained_native_cell_count=len(cells),
            retained_native_gate_count=len(positions),
            future_stage_reachability_proved=True,
        ),
    )


def deepest_native_stage(geometry, doors, entry):
    """Select a local final native region by maximum mandatory gate depth."""
    adjacency = defaultdict(set)
    for a, b in geometry["edges"]:
        a, b = tuple(a), tuple(b)
        adjacency[a].add(b)
        adjacency[b].add(a)
    blocked = {tuple(d[k] for k in ("x", "y", "z")) for d in doors}
    labels, _ = components(set(map(tuple, geometry["cells"])) - blocked, adjacency)
    representatives = {}
    for cell, region in labels.items():
        representatives.setdefault(region, cell)
    candidates = []
    for target in representatives.values():
        try:
            topology = build(geometry, doors, entry, target)
        except ValueError:
            continue
        candidates.append(topology)
    if not candidates:
        raise ValueError("No directed-reachable native bridge-separated final region")
    topology = max(
        candidates,
        key=lambda t: (
            len(t["rooms"]),
            len(t["rooms"][-1]["cells"]),
            tuple(t["rooms"][-1]["anchor"]),
        ),
    )
    topology["local_mainspine_evidence"][
        "final_stage_selection"
    ] = "Explicit local deepest mandatory-gate native region; exterior return is separately validated"
    return topology
