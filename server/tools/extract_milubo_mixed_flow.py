"""Freeze Milubo's literal mixed transport graph and four-arena stage proposal.

This is an offline topology proposal, not a runtime activation. Room assignment
uses reviewed four-arena native terrain; directed witnesses include literal
same-stage teleports instead of pretending each walk component is a room.
"""
from collections import defaultdict, deque
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_dungeon_topology import components


def hybrid_path(edges, transports, start, target, *, blocked=()):
    """Return a literal directed walking/transport witness without guessed edges."""
    blocked = set(map(tuple, blocked))
    start = tuple(start)
    target = tuple(target)
    if start in blocked or target in blocked:
        return None
    graph = defaultdict(list)
    for a, b in edges:
        a, b = tuple(a), tuple(b)
        if a not in blocked and b not in blocked:
            graph[a].append(
                (b, dict(kind="walk", from_position=list(a), to_position=list(b)))
            )
    for transport in transports:
        destination = tuple(transport["destination_position"])
        if destination in blocked:
            continue
        for approach in transport["native_approach_cells"]:
            approach = tuple(approach)
            if approach not in blocked:
                graph[approach].append(
                    (
                        destination,
                        dict(
                            kind="native_transport",
                            source_id=transport["source_id"],
                            destination_id=transport["destination_id"],
                            from_position=list(approach),
                            to_position=list(destination),
                        ),
                    )
                )
    queue = deque([start])
    seen = {start: None}
    steps = {}
    while queue:
        position = queue.popleft()
        if position == target:
            result = []
            while seen[position] is not None:
                result.append(steps[position])
                position = seen[position]
            return list(reversed(result))
        for following, step in graph[position]:
            if following not in seen:
                seen[following] = position
                steps[following] = step
                queue.append(following)
    return None


def main():
    load = lambda p: json.loads(Path(p).read_text())
    geometry = load(
        ".runtime/local/all-native-dungeon-exploration/exploration-1266.json"
    )
    inventory = next(
        r
        for r in load("docs/reports/dungeons/inventory.json")["records"]
        if r["key"] == "native:47"
    )
    route = next(
        r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
        if r["key"] == "native:47"
    )["route"]
    sources = [
        s
        for s in load(
            ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
        )
        if s["map_id"] == 1266
    ]
    physical = [
        o
        for o in inventory["native_objects"]
        if o["type"] == "Door" and o["map_id"] == 1266
    ]
    positions = {tuple(int(o[k]) for k in ("x", "y", "z")) for o in physical}
    cells = set(map(tuple, geometry["cells"]))
    adj = defaultdict(set)
    for a, b in geometry["edges"]:
        adj[tuple(a)].add(tuple(b))
        adj[tuple(b)].add(tuple(a))
    labels, sizes = components(cells - positions, adj)
    # Coordinates pin native components, avoiding dependence on enumeration IDs.
    groups = [
        [(0, 0, 0)],
        [(14, 1, -1), (-15, -81, 0)],
        [(29, -15, -8), (35, -14, -27), (46, 111, 0)],
        [(35, 117, 0)],
    ]
    anchors = [[5, 7, 0], [-10, -89, 0], [46, 122, -2], [6, 116, 16]]
    arrivals = [[0, 0, 0], [14, 1, -1], [29, -15, -8], [35, 117, 0]]
    stage_by_region = {labels[p]: i for i, group in enumerate(groups, 1) for p in group}
    rooms = [
        dict(
            order=i,
            anchor=anchors[i - 1],
            native_arrival=arrivals[i - 1],
            cells=[
                list(p)
                for p in sorted(cells - positions)
                if stage_by_region.get(labels[p]) == i
            ],
            native_component_ids=[labels[p] for p in groups[i - 1]],
        )
        for i in range(1, 5)
    ]
    assigned = {tuple(p): r["order"] for r in rooms for p in r["cells"]}
    doors = []
    exits = []
    for source in sources:
        approaches = {
            tuple(p[k] for k in ("x", "y", "z"))
            for p in source.get("approach_positions", [])
        }
        center = tuple(int(source[k]) for k in ("x", "y", "z"))
        if source.get("approach_blocks_center") is False:
            approaches.add(center)
        memberships = {assigned[p] for p in approaches if p in assigned}
        if len(memberships) != 1:
            raise ValueError("Literal source approach has no unique mixed stage")
        source_room = next(iter(memberships))
        for destination in source["destinations"]:
            if (
                destination.get("criterion", "").strip()
                or destination.get("cyZ", -1) >= 0
                or destination.get("cyX", 0)
                or destination.get("cyW", 0)
            ):
                raise ValueError("Unsupported native transport criterion/transaction")
            binding = dict(
                source_id=source["id"],
                source_room=source_room,
                destination_id=destination["destination_id"],
                source_position=list(center),
                native_approach_cells=[
                    list(p)
                    for p in sorted(approaches)
                    if assigned.get(p) == source_room
                ],
            )
            if destination["map_id"] == 1266:
                target = tuple(destination[k] for k in ("x", "y", "z"))
                binding.update(
                    destination_room=assigned[target],
                    destination_position=list(target),
                    same_stage=assigned[target] == source_room,
                )
                doors.append(binding)
            else:
                exits.append(
                    dict(
                        source_id=source["id"],
                        room_order=source_room,
                        destination_id=destination["destination_id"],
                        destination={
                            k: destination[k] for k in ("map_id", "x", "y", "z")
                        },
                        native_approach_cells=binding["native_approach_cells"],
                    )
                )
    physical_bindings = []
    for source in physical:
        center = tuple(int(source[k]) for k in ("x", "y", "z"))
        adjacent = sorted({assigned[p] for p in adj[center] if p in assigned})
        if len(adjacent) != 2:
            raise ValueError(
                "Physical gate does not separate exactly two reviewed stages"
            )
        physical_bindings.append(
            dict(
                source_id=source["id"],
                position=list(center),
                source_room=adjacent[0],
                destination_room=adjacent[1],
            )
        )
    topology = dict(
        asset_map_id=1266,
        policy="native_mixed_victory_policy",
        official_room_order_verified=False,
        progression_authority="Reviewed native four-arena linear mixed graph; tiny transit components retained within adjacent encounter stages; encounter quantities independently reviewed",
        rooms=rooms,
        doors=doors,
        physical_doors=physical_bindings,
        physical_exit_objects=exits,
        exploration_geometry=geometry,
    )
    witnesses = []
    for stage, room in enumerate(rooms, 1):
        blocked = [
            b["position"] for b in physical_bindings if b["destination_room"] > stage
        ]
        available = [
            d for d in doors if max(d["source_room"], d["destination_room"]) <= stage
        ]
        path = hybrid_path(
            geometry["edges"], available, [0, 0, 0], room["anchor"], blocked=blocked
        )
        if path is None:
            raise ValueError(f"Stage {stage} anchor has no directed mixed-native path")
        inaccessible_before = (
            stage == 1
            or hybrid_path(
                geometry["edges"],
                [
                    d
                    for d in doors
                    if max(d["source_room"], d["destination_room"]) < stage
                ],
                [0, 0, 0],
                room["anchor"],
                blocked=[
                    b["position"]
                    for b in physical_bindings
                    if b["destination_room"] >= stage
                ],
            )
            is None
        )
        if not inaccessible_before:
            raise ValueError(f"Stage {stage} is reachable before previous victory")
        witnesses.append(
            dict(
                stage=stage,
                anchor=room["anchor"],
                unreachable_before_previous_victory=inaccessible_before,
                path=path,
                native_transport_sequence=[
                    s["source_id"] for s in path if s["kind"] == "native_transport"
                ],
            )
        )
    target = Path("docs/reports/dungeons/MILUBO-MIXED-NATIVE-FLOW-20261010.json")
    target.write_text(
        json.dumps(
            dict(
                scope="Offline four-stage topology proposal; no runtime writes",
                route=route,
                topology=topology,
                component_sizes=sizes,
                component_stage_assignments=stage_by_region,
                stage_witnesses=witnesses,
                root_cause="Physical gates were removed for connected-region extraction but never reintroduced in the transport-only graph. Transport-only reachability therefore stopped in the entry component. Native walk components are not equivalent to dungeon encounter rooms.",
            ),
            indent=2,
        )
        + "\n"
    )
    print(target)


if __name__ == "__main__":
    main()
