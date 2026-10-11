"""Exhaustive read-only classic dungeon literal PositionTrigger separator audit."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from extract_dungeon_topology import components


def witness(edges, start, target, blocked):
    adjacency = defaultdict(list)
    for a, b in edges:
        adjacency[tuple(a)].append(tuple(b))
    start, target = tuple(start), tuple(target)
    if start in blocked or target in blocked:
        return None
    parents = {start: None}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        if cell == target:
            path = []
            while cell is not None:
                path.append(list(cell))
                cell = parents[cell]
            return path[::-1]
        for neighbor in adjacency[cell]:
            if neighbor not in blocked and neighbor not in parents:
                parents[neighbor] = cell
                queue.append(neighbor)
    return None


def analyze(geometry, objects):
    cells = set(map(tuple, geometry["cells"]))
    adjacency = defaultdict(set)
    for a, b in geometry["edges"]:
        adjacency[tuple(a)].add(tuple(b))
        adjacency[tuple(b)].add(tuple(a))
    doors = {
        tuple(o[k] for k in ("x", "y", "z")) for o in objects if o["type"] == "Door"
    } & cells
    triggers = [o for o in objects if o["type"] == "PositionTrigger"]
    trigger_cells = {tuple(o[k] for k in ("x", "y", "z")) for o in triggers} & cells
    _, before = components(cells - doors, adjacency)
    labels, after = components(cells - doors - trigger_cells, adjacency)
    groups = defaultdict(list)
    records = []
    for obj in triggers:
        position = tuple(obj[k] for k in ("x", "y", "z"))
        neighbors = sorted({labels[n] for n in adjacency[position] if n in labels})
        groups[tuple(neighbors)].append(obj)
        records.append(
            dict(
                object_id=obj["id"],
                literal_position=list(position),
                literal_walkable=position in cells,
                adjacent_regions=neighbors,
                payload_activation_cells_status="not_decoded_no_inferred_replacement",
            )
        )
    bundles = []
    for regions, objects_in_group in groups.items():
        if len(regions) < 2:
            continue
        boundary = {tuple(o[k] for k in ("x", "y", "z")) for o in objects_in_group}
        witnesses = []
        for left in regions:
            for right in regions:
                if left == right:
                    continue
                starts = sorted(
                    c
                    for c in labels
                    if labels[c] == left and any(n in boundary for n in adjacency[c])
                )
                ends = sorted(
                    c
                    for c in labels
                    if labels[c] == right and any(n in boundary for n in adjacency[c])
                )
                if not starts or not ends:
                    continue
                start, end = starts[0], ends[0]
                opened = witness(
                    geometry["edges"], start, end, doors | (trigger_cells - boundary)
                )
                closed = witness(geometry["edges"], start, end, doors | trigger_cells)
                if opened:
                    witnesses.append(
                        dict(
                            from_region=left,
                            to_region=right,
                            open_path=opened,
                            closed_path=closed,
                            closed_unreachable=closed is None,
                        )
                    )
        singles = []
        for obj in objects_in_group:
            cell = tuple(obj[k] for k in ("x", "y", "z"))
            singles.append(
                dict(
                    object_id=obj["id"],
                    alone_separates_any_witness=any(
                        witness(
                            geometry["edges"],
                            w["open_path"][0],
                            w["open_path"][-1],
                            doors | {cell},
                        )
                        is None
                        for w in witnesses
                    ),
                )
            )
        bundles.append(
            dict(
                object_ids=[o["id"] for o in objects_in_group],
                cells=sorted(map(list, boundary)),
                regions=list(regions),
                nonadjacent_members=any(
                    b not in adjacency[a] for a in boundary for b in boundary if a != b
                ),
                directed_witnesses=witnesses,
                single_cut_checks=singles,
                status="directed_literal_separator_candidate"
                if any(w["closed_unreachable"] for w in witnesses)
                else "no_directed_separator_proved",
            )
        )
    return dict(
        status="literal_separator_candidates"
        if any(b["status"] == "directed_literal_separator_candidate" for b in bundles)
        else "no_literal_separator_proved",
        door_only_component_sizes=before,
        all_trigger_cut_component_sizes=after,
        triggers=records,
        bundles=bundles,
        authority="Graph candidate only; trigger mechanism, gameplay stage ownership and runtime blocking not certified",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        type=Path,
        default=Path(
            "docs/reports/dungeons/ALL-CLASSIC-HYBRID-STRUCTURE-AUDIT-20261010.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "docs/reports/dungeons/ALL-CLASSIC-POSITION-TRIGGER-CUTS-V2-20261010.json"
        ),
    )
    args = parser.parse_args()
    inventory_path = Path("docs/reports/dungeons/inventory.json")
    scope_path = args.scope
    inventory = {r["key"]: r for r in json.loads(inventory_path.read_text())["records"]}
    scope = json.loads(scope_path.read_text())["definition_coverage"]
    records = []
    for definition in scope:
        record = inventory[definition["key"]]
        map_ids = {o["map_id"] for o in record.get("native_objects", [])} | {
            r["start_map_id"] for r in record.get("native_entry_routes", [])
        }
        maps = []
        for map_id in sorted(map_ids):
            objects = [
                o for o in record.get("native_objects", []) if o["map_id"] == map_id
            ]
            path = Path(
                f".runtime/local/all-native-dungeon-exploration/exploration-{map_id}.json"
            )
            count = sum(o["type"] == "PositionTrigger" for o in objects)
            item = dict(map_id=map_id, trigger_count=count, geometry_path=str(path))
            if not path.exists():
                item["status"] = "missing_geometry"
            else:
                item["geometry_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                if count:
                    item.update(analyze(json.loads(path.read_text()), objects))
                else:
                    item["status"] = "no_native_position_triggers"
            maps.append(item)
        records.append(
            dict(
                key=definition["key"],
                name=definition["name"],
                native_name=definition["native_name"],
                configuration_scopes=definition["audited_configurations"],
                maps=maps,
                status="maps_audited" if maps else "no_native_maps_available",
            )
        )
    result = dict(
        schema_version=3,
        scope="All classic definitions/names in the selected structure report; no component-size threshold",
        scope_report=str(scope_path),
        inventory_sha256=hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        scope_sha256=hashlib.sha256(scope_path.read_bytes()).hexdigest(),
        definition_count=len(records),
        map_status_counts=dict(
            Counter(m["status"] for r in records for m in r["maps"])
        ),
        records=records,
        recovered_dungeons=0,
    )
    path = args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                path=str(path),
                definition_count=len(records),
                map_status_counts=result["map_status_counts"],
            )
        )
    )


if __name__ == "__main__":
    main()
