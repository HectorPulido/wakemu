"""Batch native exploration flow evidence; offline, no runtime or database writes."""
import argparse
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_native_door_flow import extract
from extract_dungeon_topology import analyze


def reachable(edges, entry, blocked=()):
    adjacency = defaultdict(list)
    for a, b in edges:
        adjacency[tuple(a)].append(tuple(b))
    blocked = set(map(tuple, blocked))
    entry = tuple(entry)
    seen = set() if entry in blocked else {entry}
    queue = deque(seen)
    while queue:
        for target in adjacency[queue.popleft()]:
            if target not in seen and target not in blocked:
                seen.add(target)
                queue.append(target)
    return seen


def classify(geometry, objects, entry, exits, teleports):
    """Keep exact native arrivals; never replace them by a nearest terrain cell."""
    cells = set(map(tuple, geometry["cells"]))
    if tuple(entry) not in cells:
        return dict(status="entry_not_walkable", entry=entry, manual_review=True)
    doors = [o for o in objects if o["type"] == "Door"]
    blocked = [tuple(o[k] for k in ("x", "y", "z")) for o in doors]
    first = reachable(geometry["edges"], entry, blocked)
    topology = analyze(geometry, objects, [entry], teleports)
    flows = []
    for target in exits:
        result = extract(geometry, doors, entry, target)
        if (
            result["status"] == "physical_linear_chain_proved"
            and result["door_chain"]
            and all(not s["exit_reachable"] for s in result["stages"][:-1])
        ):
            flows.append(result)
    chains = {tuple(f["door_chain"]) for f in flows}
    status = (
        "mixed_transport_physical_review"
        if chains and teleports
        else "physical_linear_chain_proved"
        if len(chains) == 1
        else "physical_chain_ambiguous"
        if len(chains) > 1
        else "native_transport_graph_review"
        if teleports
        else "open_geometry_no_separator"
        if not any(d["candidate_separator"] for d in topology["doors"])
        else "physical_flow_review"
    )
    return dict(
        status=status,
        entry=list(entry),
        first_encounter_reachable_cells=[list(c) for c in sorted(first)],
        first_encounter_cell_count=len(first),
        directed_physical_flows=flows,
        topology=topology,
        native_internal_teleports=teleports,
        manual_review=status != "physical_linear_chain_proved",
        authority="Native directed exploration geometry and literal transport endpoints; victory unlocks and rosters require explicit DEV policy",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--inventory", type=Path, default=Path("docs/reports/dungeons/inventory.json")
    )
    p.add_argument(
        "--snapshot",
        type=Path,
        default=Path(".runtime/local/methodwakfu-dungeons/inventory-native-snapshot"),
    )
    p.add_argument("--geometry-dir", type=Path, required=True)
    p.add_argument("--templates-dir", type=Path)
    p.add_argument("--classes", default=".runtime/local/tofu-native-flow/classes")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    records = json.loads(args.inventory.read_text())["records"]
    transport = json.loads(
        (args.snapshot / "native-generic-teleporters.json").read_text()
    )
    by_source = {(r["map_id"], r["id"]): r for r in transport}
    maps = sorted(
        {route["start_map_id"] for r in records for route in r["native_entry_routes"]}
    )
    args.geometry_dir.mkdir(parents=True, exist_ok=True)

    def export(map_id):
        path = args.geometry_dir / f"exploration-{map_id}.json"
        if not path.exists():
            result = subprocess.run(
                [
                    "java",
                    "-cp",
                    args.classes + ":client/lib/*",
                    "ExportNativeExplorationMap",
                    str(map_id),
                    str(path),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode:
                return map_id, {"export_error": result.stderr[-1000:]}
        return map_id, json.loads(path.read_text())

    geometries = dict(ThreadPoolExecutor(max_workers=2).map(export, maps))
    results = []
    for record in records:
        for route in record["native_entry_routes"]:
            row = dict(key=record["key"], name=record.get("name_es"), route=route)
            geometry = geometries[route["start_map_id"]]
            source = by_source.get(
                (route["entry_map_id"], route["entry_object_id"]), {}
            )
            destinations = [
                d
                for d in source.get("destinations", [])
                if d["destination_id"] == route["destination_id"]
                and d["map_id"] == route["start_map_id"]
            ]
            if "export_error" in geometry or len(destinations) != 1:
                row.update(
                    status="native_entry_or_geometry_missing", manual_review=True
                )
            else:
                map_id = geometry["map_id"]
                exits = [
                    tuple(o[k] for k in ("x", "y", "z"))
                    for o in record["native_objects"]
                    if o["map_id"] == map_id
                    and any(
                        e["source_object"] == o["id"] and e["source_map"] == map_id
                        for e in record["native_exits"]
                    )
                ]
                teleports = [
                    t
                    for t in transport
                    if t["map_id"] == map_id
                    and any(
                        d["map_id"]
                        in set(record.get("native", {}).get("raw_aHA", [map_id]))
                        for d in t["destinations"]
                    )
                ]
                row.update(
                    classify(
                        geometry,
                        [o for o in record["native_objects"] if o["map_id"] == map_id],
                        [destinations[0][k] for k in ("x", "y", "z")],
                        exits,
                        teleports,
                    )
                )
            if (
                args.templates_dir
                and row.get("status") == "physical_linear_chain_proved"
            ):
                from build_physical_dungeon_configuration import topology_for

                args.templates_dir.mkdir(parents=True, exist_ok=True)
                flow = row["directed_physical_flows"][0]
                candidate = topology_for(
                    geometry,
                    [
                        o
                        for o in record["native_objects"]
                        if o["map_id"] == geometry["map_id"] and o["type"] == "Door"
                    ],
                    row["entry"],
                    flow["exit"],
                    [],
                )
                # This is a candidate topology, never an installable runtime
                # configuration: rosters, encounter formations and validated
                # exterior exit objects must be supplied independently.
                candidate[
                    "generation_status"
                ] = "requires_roster_formation_and_exit_validation"
                target = args.templates_dir / (route["key"] + ".json")
                target.write_text(json.dumps(candidate, indent=2) + "\n")
                row["candidate_topology_path"] = str(target)
            results.append(row)
    report = dict(
        schema_version=1,
        scope="Offline candidate generation; never automatically activates gameplay",
        native_map_count=len(maps),
        route_count=len(results),
        definitions_without_entry_route=[
            r["key"] for r in records if not r["native_entry_routes"]
        ],
        coverage=dict(Counter(r["status"] for r in results)),
        records=results,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
