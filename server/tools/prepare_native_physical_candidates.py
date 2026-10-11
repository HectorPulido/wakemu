"""Prepare offline physical dungeon candidates with literal native exit contracts."""
import argparse
import copy
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_physical_dungeon_configuration import build


def completed_exit_witness(topology, bindings, transports):
    """Prove a unique non-entry exit via literal adjacent backward transports."""
    from extract_native_door_flow import shortest_path

    if topology.get("policy") != "native_teleport_victory_policy":
        raise ValueError("Indirect final exits require a native teleport policy")
    rooms = {r["order"]: set(map(tuple, r["cells"])) for r in topology["rooms"]}
    geometry = topology["exploration_geometry"]
    catalog = {(s["map_id"], s["id"]): s for s in transports}
    final = max(rooms)
    start = tuple(topology["rooms"][-1]["anchor"])
    queue = [(final, start, [])]
    seen, witnesses, entry_witnesses = set(), [], []
    while queue:
        room, position, steps = queue.pop(0)
        if (room, position) in seen:
            continue
        seen.add((room, position))
        edges = [
            (a, b)
            for a, b in geometry["edges"]
            if tuple(a) in rooms[room] and tuple(b) in rooms[room]
        ]
        for binding in bindings:
            if binding["room_order"] != room:
                continue
            for approach in binding["native_approach_cells"]:
                path = shortest_path(edges, position, approach)
                if path:
                    (entry_witnesses if room == 1 else witnesses).append(
                        dict(
                            source_id=binding["source_id"],
                            room_order=room,
                            steps=steps
                            + [
                                dict(
                                    kind="exterior_exit",
                                    source_id=binding["source_id"],
                                    destination_id=binding["destination_id"],
                                    walking_path=path,
                                    destination=binding["destination"],
                                )
                            ],
                        )
                    )
                    break
        for door in topology.get("doors", ()):
            if door["source_room"] != room or door["destination_room"] != room - 1:
                continue
            source = catalog.get((topology["asset_map_id"], door["source_id"]))
            if source is None:
                continue
            destination = next(
                (
                    d
                    for d in source["destinations"]
                    if d["destination_id"] == door["destination_id"]
                ),
                None,
            )
            if destination is None or destination["map_id"] != topology["asset_map_id"]:
                continue
            if (
                destination.get("criterion", "").strip()
                or destination.get("cyZ", -1) >= 0
                or destination.get("cyX", 0)
                or (
                    destination.get("cyW", 0) > 0
                    and destination.get("item_reference", 0) > 0
                )
                or destination.get("native_altitude_walkable") is not True
            ):
                continue
            arrival = tuple(destination[k] for k in ("x", "y", "z"))
            literal = {
                tuple(a[k] for k in ("x", "y", "z"))
                for a in source.get("approach_positions", ())
            }
            if source.get("approach_blocks_center") is False:
                literal.add(tuple(source[k] for k in ("x", "y", "z")))
            if (
                arrival not in rooms[room - 1]
                or list(arrival) != door["destination_position"]
                or tuple(source[k] for k in ("x", "y", "z"))
                != tuple(door["source_position"])
            ):
                continue
            for approach in door["native_approach_cells"]:
                if tuple(approach) not in literal:
                    continue
                path = shortest_path(edges, position, approach)
                if path:
                    queue.append(
                        (
                            room - 1,
                            arrival,
                            steps
                            + [
                                dict(
                                    kind="backward_transport",
                                    source_id=source["id"],
                                    destination_id=destination["destination_id"],
                                    source_room=room,
                                    destination_room=room - 1,
                                    walking_path=path,
                                    destination_position=list(arrival),
                                )
                            ],
                        )
                    )
                    break
    # Prefer a dedicated completed-run exit. A room-one cancellation exit is
    # also a completion path only after a fully proved literal backward chain.
    if not witnesses:
        witnesses = [
            w
            for w in entry_witnesses
            if any(step["kind"] == "backward_transport" for step in w["steps"])
        ]
    if len({w["source_id"] for w in witnesses}) != 1:
        raise ValueError(
            "No unique directed native completed-run exit via backward transports"
        )
    return witnesses[0]


def bind_exits(topology, route, transports, *, allow_physical_return=False):
    """Require literal approach cells, free native destination and unique ends."""
    rooms = {r["order"]: set(map(tuple, r["cells"])) for r in topology["rooms"]}
    bindings = []
    for source in transports:
        if source["map_id"] != topology["asset_map_id"]:
            continue
        destinations = [
            d for d in source["destinations"] if d["map_id"] == route["entry_map_id"]
        ]
        if len(destinations) != 1:
            continue
        d = destinations[0]
        if (
            d.get("criterion", "").strip()
            or d.get("cyZ", -1) >= 0
            or d.get("cyX", 0)
            or (d.get("cyW", 0) > 0 and d.get("item_reference", 0) > 0)
            or d.get("native_altitude_walkable") is not True
        ):
            continue
        approaches = {
            tuple(a[k] for k in ("x", "y", "z"))
            for a in source.get("approach_positions", [])
        }
        if source.get("approach_blocks_center") is False:
            approaches.add(tuple(int(source[k]) for k in ("x", "y", "z")))
        memberships = [order for order, cells in rooms.items() if cells & approaches]
        if len(memberships) != 1:
            continue
        bindings.append(
            dict(
                source_id=source["id"],
                room_order=memberships[0],
                destination_id=d["destination_id"],
                destination={k: d[k] for k in ("map_id", "x", "y", "z")},
                native_approach_cells=[
                    list(c) for c in sorted(approaches & rooms[memberships[0]])
                ],
            )
        )
    if sum(b["room_order"] == 1 for b in bindings) != 1:
        raise ValueError("No unique free native exterior exit for room 1")
    final_count = sum(b["room_order"] == len(rooms) for b in bindings)
    if final_count > 1:
        raise ValueError(f"No unique free native exterior exit for room {len(rooms)}")
    if final_count == 0:
        if (
            allow_physical_return
            and topology.get("policy") == "native_physical_door_victory_policy"
        ):
            from extract_native_door_flow import shortest_path

            final_anchor = topology["rooms"][-1]["anchor"]
            entrances = [b for b in bindings if b["room_order"] == 1]
            paths = [
                (
                    b,
                    shortest_path(
                        topology["exploration_geometry"]["edges"],
                        final_anchor,
                        approach,
                    ),
                )
                for b in entrances
                for approach in b["native_approach_cells"]
            ]
            proved = [(b, path) for b, path in paths if path]
            if not proved:
                raise ValueError(
                    "No directed native walking return from final stage to exterior exit"
                )
            binding, path = proved[0]
            topology["completed_exit_witness"] = dict(
                kind="physical_return_walk",
                source_id=binding["source_id"],
                room_order=1,
                walking_path=path,
                destination=binding["destination"],
            )
        else:
            topology["completed_exit_witness"] = completed_exit_witness(
                topology, bindings, transports
            )
    return bindings


def normalized_roster(roster, native):
    result = copy.deepcopy(roster)
    pool = {m["ref_id"]: m for m in native["native_species_pool"]}
    if any(m.get("ref_id") not in pool for r in result["rooms"] for m in r["monsters"]):
        raise ValueError("Roster contains unresolved or non-native monster identities")
    for room in result["rooms"]:
        room["monsters"] = [
            dict(
                name=m["name"],
                ref_id=m["ref_id"],
                count=m["count"],
                role=m.get("role", "monster"),
                native_min_level=pool[m["ref_id"]]["min_level"],
                native_max_level=pool[m["ref_id"]]["max_level"],
                guide_min_level=m.get("min_level"),
                guide_max_level=m.get("max_level"),
            )
            for m in room["monsters"]
        ]
    return result


def main():
    from wakfu_server import dungeon_physical_doors
    from wakfu_server.dungeon_runtime_config import plan_from_configuration

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compositions",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-COMPOSITION-COVERAGE.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".runtime/local/native-physical-complete-candidates"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-COMPLETE-CANDIDATES.json"),
    )
    args = parser.parse_args()
    root = Path(".runtime/local")
    inventory = json.loads(Path("docs/reports/dungeons/inventory.json").read_text())[
        "records"
    ]
    compositions = json.loads(args.compositions.read_text())["records"]
    flows = json.loads((root / "all-native-dungeon-flows.json").read_text())["records"]
    bases = json.loads(
        (
            root / "methodwakfu-dungeons/local-policy-configs-all87/configurations.json"
        ).read_text()
    )["configurations"]
    transports = json.loads(
        (
            root
            / "methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
        ).read_text()
    )
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for row in compositions:
        if row["status"] != "roster_candidate_prepared":
            continue
        item = dict(key=row["key"], name=row["name"], route=row["route"])
        try:
            native = next(r for r in inventory if r["key"] == row["key"])
            flow = next(r for r in flows if r["route"]["key"] == row["route"])
            route = flow["route"]
            base = next(b for b in bases if b["route"]["key"] == row["route"])
            topology = json.loads(Path(flow["candidate_topology_path"]).read_text())
            exits = bind_exits(topology, route, transports)
            geometry = json.loads(
                (
                    root
                    / f'all-native-dungeon-exploration/exploration-{route["start_map_id"]}.json'
                ).read_text()
            )
            candidate = build(
                base,
                geometry,
                normalized_roster(row["roster_candidate"], native),
                [
                    o
                    for o in native["native_objects"]
                    if o["type"] == "Door" and o["map_id"] == route["start_map_id"]
                ],
                flow["entry"],
                flow["directed_physical_flows"][0]["exit"],
                exits,
                base["version"] + 1,
            )
            plan_from_configuration(candidate)
            packet_count = 0
            for stage in range(1, len(candidate["topology"]["rooms"]) + 1):
                packets = dungeon_physical_doors.packets(
                    dict(candidate["topology"], physical_exit_objects=[]),
                    map_id=route["start_map_id"],
                    instance_id=42,
                    unlocked_room=stage,
                )
                if any(opcode != 12344 or len(body) < 21 for opcode, body in packets):
                    raise ValueError("Native interactive-state packet layout invalid")
                packet_count += len(packets)
            path = output / (row["route"] + ".json")
            path.write_text(json.dumps(candidate, indent=2) + "\n")
            item.update(
                status="offline_configuration_prepared",
                path=str(path),
                exits=exits,
                activation_readiness="requires_full_flow_and_boss_mechanic_validation",
                boss_mechanic_status="not_proved",
                protocol_state_packet_count=packet_count,
                rooms=len(candidate["topology"]["rooms"]),
            )
        except (ValueError, KeyError, StopIteration) as error:
            item.update(status="unsupported", reason=str(error) or type(error).__name__)
        results.append(item)
    report = dict(
        scope="Offline preparation only; no runtime activation", records=results
    )
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
