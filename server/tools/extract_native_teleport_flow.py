"""Offline natural transport sequencing from literal native approaches and arrivals."""
from collections import defaultdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_dungeon_topology import components
from extract_native_door_flow import shortest_path


def extract(geometry, objects, entry, transports):
    cells = set(map(tuple, geometry["cells"]))
    blocked = {
        tuple(o[k] for k in ("x", "y", "z")) for o in objects if o["type"] == "Door"
    }
    adjacency = defaultdict(set)
    for a, b in geometry["edges"]:
        a, b = tuple(a), tuple(b)
        adjacency[a].add(b)
        adjacency[b].add(a)
    labels, sizes = components(cells - blocked, adjacency)
    entry = tuple(entry)
    if entry not in labels:
        return dict(status="native_entry_unresolved", manual_review=True)
    links = []
    unresolved = []
    for source in transports:
        approaches = {
            tuple(a[k] for k in ("x", "y", "z"))
            for a in source.get("approach_positions", [])
        }
        if source.get("approach_blocks_center") is False:
            approaches.add(tuple(int(source[k]) for k in ("x", "y", "z")))
        approaches = approaches & labels.keys()
        for destination in source["destinations"]:
            if destination["map_id"] != geometry["map_id"]:
                unresolved.append(
                    dict(
                        source_id=source["id"],
                        destination_id=destination["destination_id"],
                        reason="cross_map_transition_requires_separate_geometry",
                    )
                )
                continue
            target = tuple(destination[k] for k in ("x", "y", "z"))
            source_regions = {labels[p] for p in approaches}
            if len(source_regions) != 1 or target not in labels:
                unresolved.append(
                    dict(
                        source_id=source["id"],
                        destination_id=destination["destination_id"],
                        reason="literal_approach_or_arrival_not_resolved",
                        source_regions=sorted(source_regions),
                        destination_position=target,
                    )
                )
                continue
            links.append(
                dict(
                    source_id=source["id"],
                    destination_id=destination["destination_id"],
                    source_region=next(iter(source_regions)),
                    destination_region=labels[target],
                    approaches=[list(p) for p in sorted(approaches)],
                    destination_position=list(target),
                    criterion=destination.get("criterion", ""),
                    requires_item=destination.get("cyW", 0) > 0
                    and destination.get("item_reference", 0) > 0,
                    requires_kamas=destination.get("cyX", 0) != 0,
                    instance_template=destination.get("cyZ", -1),
                )
            )
    chain = [labels[entry]]
    stages = []
    current = entry
    status = "native_teleport_linear_chain_proved"
    while True:
        forward = [
            l
            for l in links
            if l["source_region"] == chain[-1] and l["destination_region"] not in chain
        ]
        next_regions = {l["destination_region"] for l in forward}
        if not forward:
            break
        if len(next_regions) != 1:
            status = "branched_native_transport_graph"
            break
        alternatives = []
        for link in forward:
            for approach in link["approaches"]:
                path = shortest_path(geometry["edges"], current, approach, blocked)
                if path:
                    alternatives.append(dict(transport=link, directed_walk_path=path))
                    break
        if not alternatives:
            status = "directed_native_transport_approach_unreachable"
            break
        selected = alternatives[0]
        stages.append(
            dict(
                source_region=chain[-1],
                destination_region=selected["transport"]["destination_region"],
                alternatives=alternatives,
            )
        )
        chain.append(selected["transport"]["destination_region"])
        current = tuple(selected["transport"]["destination_position"])
    connected = {labels[entry]}
    while True:
        expanded = connected | {
            l["destination_region"] for l in links if l["source_region"] in connected
        }
        if expanded == connected:
            break
        connected = expanded
    if status == "native_teleport_linear_chain_proved":
        if unresolved:
            status = "unresolved_native_transport_endpoints"
        elif connected != set(chain):
            status = "transport_chain_incomplete"
        elif len(chain) == 1:
            status = "transports_within_same_physical_region"
        elif any(
            l["requires_item"] or l["requires_kamas"] or l["instance_template"] >= 0
            for l in links
        ):
            status = "transport_sequence_requires_unsupported_transaction"
        elif any(l["criterion"].strip() for l in links):
            status = "physical_sequence_with_unverified_criteria"
    return dict(
        status=status,
        manual_review=status != "native_teleport_linear_chain_proved",
        map_id=geometry["map_id"],
        entry=list(entry),
        region_chain=chain,
        room_cell_counts=[sizes[i] for i in chain],
        stages=stages,
        native_links=links,
        unresolved=unresolved,
        topology_sha256=geometry.get("topology_sha256"),
        client_sha256=geometry.get("client_sha256"),
        limits="Literal native movement and transport sequence only; fight completion requirements, encounter bindings and boss mechanics require separate evidence",
    )


def topology_for(geometry, objects, entry, transports, flow):
    """Generate a candidate topology from proved directed native transport order."""
    from extract_all_dungeon_flows import reachable

    if flow["status"] != "native_teleport_linear_chain_proved":
        raise ValueError("Native transport sequence is not proved")
    blocked = {
        tuple(o[k] for k in ("x", "y", "z")) for o in objects if o["type"] == "Door"
    }
    cells = set(map(tuple, geometry["cells"])) - blocked
    adjacency = defaultdict(set)
    for a, b in geometry["edges"]:
        a, b = tuple(a), tuple(b)
        adjacency[a].add(b)
        adjacency[b].add(a)
    labels, _ = components(cells, adjacency)
    rooms = []
    arrivals = [list(entry)] + [
        s["alternatives"][0]["transport"]["destination_position"]
        for s in flow["stages"]
    ]
    for order, (region, arrival) in enumerate(zip(flow["region_chain"], arrivals), 1):
        selected = sorted(p for p, label in labels.items() if label == region)
        accessible = reachable(geometry["edges"], arrival, blocked) & set(selected)
        if not accessible:
            raise ValueError("Native room arrival cannot reach its region")
        n = len(accessible)
        sx = sum(p[0] for p in accessible)
        sy = sum(p[1] for p in accessible)
        anchor = min(
            accessible, key=lambda p: ((p[0] * n - sx) ** 2 + (p[1] * n - sy) ** 2, p)
        )
        rooms.append(
            dict(
                order=order,
                anchor=list(anchor),
                cells=[list(p) for p in selected],
                native_arrival=list(arrival),
            )
        )
    order_by_region = {region: i + 1 for i, region in enumerate(flow["region_chain"])}
    doors = []
    for link in flow["native_links"]:
        a = order_by_region.get(link["source_region"])
        b = order_by_region.get(link["destination_region"])
        if a is None or b is None or abs(a - b) != 1:
            continue
        source = next(t for t in transports if t["id"] == link["source_id"])
        doors.append(
            dict(
                source_id=source["id"],
                source_room=a,
                destination_room=b,
                destination_id=link["destination_id"],
                source_position=[source[k] for k in ("x", "y", "z")],
                native_approach_cells=link["approaches"],
                destination_position=link["destination_position"],
            )
        )
    return dict(
        asset_map_id=geometry["map_id"],
        policy="native_teleport_victory_policy",
        official_room_order_verified=False,
        progression_authority="Explicit DEV committed room victory gates literal native transport sequence",
        rooms=rooms,
        doors=doors,
        physical_doors=[],
        physical_exit_objects=[],
        generation_status="requires_roster_formation_exit_and_dispatch_validation",
        exploration_geometry={
            k: geometry[k]
            for k in (
                "map_id",
                "profile",
                "client_sha256",
                "topology_sha256",
                "cells",
                "edges",
            )
        },
    )


def main():
    rows = json.loads(Path(".runtime/local/all-native-dungeon-flows.json").read_text())[
        "records"
    ]
    inventory = json.loads(Path("docs/reports/dungeons/inventory.json").read_text())[
        "records"
    ]
    results = []
    for row in rows:
        if row["status"] != "native_transport_graph_review":
            continue
        native = next(r for r in inventory if r["key"] == row["key"])
        geometry = json.loads(
            Path(
                f'.runtime/local/all-native-dungeon-exploration/exploration-{row["route"]["start_map_id"]}.json'
            ).read_text()
        )
        result = extract(
            geometry,
            [o for o in native["native_objects"] if o["map_id"] == geometry["map_id"]],
            row["entry"],
            row["native_internal_teleports"],
        )
        if result["status"] == "native_teleport_linear_chain_proved":
            topology = topology_for(
                geometry,
                [
                    o
                    for o in native["native_objects"]
                    if o["map_id"] == geometry["map_id"]
                ],
                row["entry"],
                row["native_internal_teleports"],
                result,
            )
            target = Path(".runtime/local/native-teleport-topology-candidates") / (
                row["route"]["key"] + ".json"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(topology, indent=2) + "\n")
            result["candidate_topology_path"] = str(target)
        results.append(
            dict(key=row["key"], name=row["name"], route=row["route"], **result)
        )
    from collections import Counter

    report = dict(
        scope="Offline automatic transport sequence evidence; no activation",
        coverage=dict(Counter(r["status"] for r in results)),
        records=results,
    )
    Path("docs/reports/dungeons/AUTOMATIC-TELEPORT-FLOW.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report["coverage"], indent=2))


if __name__ == "__main__":
    main()
