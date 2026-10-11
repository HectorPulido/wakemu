"""Prepare explicit local final arenas retaining all native gates and terrain.

Intermediate areas have no encounters. All native gates are open at stage one;
identified family bosses appear once in the deepest reachable native region.
"""
import copy
import json
from collections import defaultdict, deque
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_family_configuration_base import base
from prepare_native_physical_candidates import bind_exits
from validate_dungeon_flow_rosters import validate
from validate_prepared_physical_flows import validate as sequence
from extract_dungeon_topology import analyze, components


def final_region(geometry, doors, entry):
    """Select deepest reachable closed region by native gate graph distance."""
    adjacency = defaultdict(set)
    directed = defaultdict(list)
    for a, b in geometry["edges"]:
        a, b = tuple(a), tuple(b)
        adjacency[a].add(b)
        adjacency[b].add(a)
        directed[a].append(b)
    positions = {tuple(d[k] for k in ("x", "y", "z")) for d in doors}
    labels, _ = components(set(map(tuple, geometry["cells"])) - positions, adjacency)
    if tuple(entry) not in labels:
        raise ValueError("Arrival is outside a closed native region")
    graph = defaultdict(set)
    analysis = analyze(geometry, doors, [entry])
    for gate in analysis["doors"]:
        regions = gate["adjacent_closed_regions"]
        for a in regions:
            for b in regions:
                if a != b:
                    graph[a].add(b)
    depths = {labels[tuple(entry)]: 0}
    queue = deque(depths)
    while queue:
        current = queue.popleft()
        for neighbor in graph[current]:
            if neighbor not in depths:
                depths[neighbor] = depths[current] + 1
                queue.append(neighbor)
    distance = {tuple(entry): 0}
    queue = deque(distance)
    while queue:
        current = queue.popleft()
        for neighbor in directed[current]:
            if neighbor not in distance:
                distance[neighbor] = distance[current] + 1
                queue.append(neighbor)
    regions = defaultdict(list)
    for cell, region in labels.items():
        if cell in distance and region in depths:
            regions[region].append(cell)
    deepest = max(depths[r] for r in regions)
    selected = max(
        (r for r in regions if depths[r] == deepest),
        key=lambda r: (max(distance[c] for c in regions[r]), len(regions[r]), r),
    )
    return regions[selected], dict(
        kind="explicit_local_deepest_native_gate_region",
        region=selected,
        native_gate_depth=deepest,
        entry_region=labels[tuple(entry)],
        reachable_region_cells=len(regions[selected]),
    )


def main():
    from wakfu_server.dungeon_physical_doors import POLICY
    from wakfu_server.dungeon_runtime_config import prepare_configuration
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    load = lambda p: json.loads(Path(p).read_text())
    inventory = {
        r["key"]: r for r in load("docs/reports/dungeons/inventory.json")["records"]
    }
    evidence = {
        r["key"]: r
        for r in load("docs/reports/dungeons/REMAINING-FAMILY-BOSSES-20261010.json")[
            "records"
        ]
    }
    flows = {
        r["key"]: r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
    }
    transports = load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    output = Path(".runtime/local/family-final-arena-candidates-20261010")
    output.mkdir(exist_ok=True)
    rows = []
    for identifier in (196, 79, 139, 68):
        key = f"native:{identifier}"
        native = inventory[key]
        flow = flows[key]
        proof = evidence[key]
        row = dict(key=key, name=native["name_es"], route=flow["route"]["key"])
        try:
            mid = flow["route"]["start_map_id"]
            geometry = load(
                f".runtime/local/all-native-dungeon-exploration/exploration-{mid}.json"
            )
            doors = [
                d
                for d in native["native_objects"]
                if d["map_id"] == mid and d["type"] == "Door"
            ]
            selected, selection = final_region(geometry, doors, flow["entry"])
            pool = {m["ref_id"]: m for m in native["native_species_pool"]}
            bosses = proof["boss_references"]
            regular = proof["family_pool_references"]
            physical = [
                dict(
                    source_id=d["id"],
                    position=[d[k] for k in ("x", "y", "z")],
                    source_room=1,
                    destination_room=1,
                    local_annex_gate=True,
                )
                for d in doors
            ]
            topology = dict(
                asset_map_id=mid,
                policy=POLICY,
                official_room_order_verified=False,
                progression_authority="User-authorized single local final family encounter; intermediate native regions have no encounters; all native gates open at stage one; all native terrain retained",
                rooms=[
                    dict(order=1, anchor=list(selected[0]), cells=geometry["cells"])
                ],
                doors=[],
                physical_doors=physical,
                physical_exit_objects=[],
                exploration_geometry=copy.deepcopy(geometry),
                local_final_region_evidence=selection,
            )
            try:
                topology["physical_exit_objects"] = bind_exits(
                    topology, flow["route"], transports, allow_physical_return=True
                )
            except ValueError:
                aliases = []
                for transport in transports:
                    try:
                        aliases.extend(
                            bind_exits(
                                topology,
                                flow["route"],
                                [transport],
                                allow_physical_return=True,
                            )
                        )
                    except ValueError:
                        continue
                destinations = {
                    tuple(e["destination"][k] for k in ("map_id", "x", "y", "z"))
                    for e in aliases
                }
                if not aliases or len(destinations) != 1:
                    raise ValueError("No unique literal native exterior destination")
                topology["equivalent_native_exit_aliases"] = aliases
                topology["physical_exit_objects"] = [
                    min(aliases, key=lambda e: e["source_id"])
                ]
            topology["rooms"][0]["cells"] = [list(c) for c in selected]
            p = published_geometry(mid)
            combat = dict(map_id=mid, cells=list(p.cells), edges=list(p.edges))
            attempts = []
            for quantity in (8, 6, 4, 3, 2, 1):
                refs = list(bosses)
                if regular:
                    refs += [
                        regular[i % len(regular)]
                        for i in range(max(0, quantity - len(bosses)))
                    ]
                monsters = [
                    dict(
                        name=pool[r]["name_es"],
                        ref_id=r,
                        count=refs.count(r),
                        role="boss" if r in bosses else "monster",
                        native_min_level=pool[r]["min_level"],
                        native_max_level=pool[r]["max_level"],
                        guide_min_level=None,
                        guide_max_level=None,
                    )
                    for r in sorted(set(refs))
                ]
                compiled = base(
                    native, flow["route"], [dict(order=1, monsters=monsters)]
                )
                for anchor in sorted(
                    selected,
                    key=lambda c: (
                        sum((c[i] - selected[0][i]) ** 2 for i in range(2)),
                        c,
                    ),
                ):
                    topology["rooms"][0]["anchor"] = list(anchor)
                    config = prepare_configuration(
                        compiled["compiled_plan"],
                        copy.deepcopy(topology),
                        flow["route"],
                        version=5,
                        provenance=topology["progression_authority"],
                    )
                    placement = validate(
                        config, geometry, combat, enemy_formation, entry=flow["entry"]
                    )
                    if placement["status"] != "candidate_validated":
                        continue
                    if any(
                        tuple(position) not in set(selected)
                        for position in placement["rooms"][0]["monster_positions"]
                    ):
                        continue
                    try:
                        traversal = sequence(
                            config, dict(entry=flow["entry"]), placement
                        )
                    except ValueError:
                        continue
                    break
                else:
                    attempts.append(
                        dict(
                            quantity=quantity,
                            reason="No deep-region formation and directed encounter/exit sequence",
                        )
                    )
                    continue
                break
            else:
                raise ValueError(
                    "No validated deep native final encounter: " + str(attempts)
                )
            path = output / (row["route"] + ".json")
            path.write_text(json.dumps(config, indent=2) + "\n")
            row.update(
                status="offline_configuration_prepared",
                path=str(path),
                rooms=1,
                boss_references=bosses,
                regular_family=regular,
                local_quantity=len(refs),
                selection=selection,
                placement_validation=placement,
                sequence_validation=traversal,
                local_policy=topology["progression_authority"],
                retained_cells=len(geometry["cells"]),
                retained_gates=len(doors),
            )
        except (ValueError, KeyError) as error:
            row.update(status="blocked", reason=str(error))
        rows.append(row)
    Path(
        "docs/reports/dungeons/FAMILY-FINAL-ARENA-CANDIDATES-20261010.json"
    ).write_text(json.dumps(dict(records=rows), indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            [(r["name"], r["status"], r.get("reason")) for r in rows],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
