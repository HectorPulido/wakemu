"""Audit every inactive classic dungeon's literal geometry without runtime writes."""
import json
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_native_door_flow import extract, shortest_path

ORDINARY_TYPES = {
    "DUNGEON_2_ROOMS",
    "DUNGEON_3_ROOMS",
    "DUNGEON_4_ROOMS",
    "DUNGEON_3_PLAYERS",
}


def ordinary(record):
    native = record.get("native") or {}
    return native.get("type") in ORDINARY_TYPES and not native.get(
        "name_fr", ""
    ).lower().startswith(("neo-", "néo-"))


def audit(record, flows, geometry_dir):
    routes = []
    for flow in flows:
        route = flow["route"]
        path = geometry_dir / f"exploration-{route['start_map_id']}.json"
        if not path.exists():
            routes.append(
                dict(route=route["key"], blocker="missing_native_exploration_geometry")
            )
            continue
        geometry = json.loads(path.read_text())
        doors = [
            o
            for o in record["native_objects"]
            if o["map_id"] == geometry["map_id"] and o["type"] == "Door"
        ]
        exits = {
            tuple(o[k] for k in ("x", "y", "z"))
            for o in record["native_objects"]
            if o["map_id"] == geometry["map_id"]
            and any(
                e["source_object"] == o["id"] and e["source_map"] == geometry["map_id"]
                for e in record["native_exits"]
            )
        }
        witnesses = []
        for target in sorted(exits):
            result = extract(geometry, doors, flow["entry"], target)
            witness = dict(
                exit_position=list(target),
                physical_status=result["status"],
                all_doors_open_exit_reachable=shortest_path(
                    geometry["edges"], flow["entry"], target
                )
                is not None,
            )
            if "door_chain" in result:
                witness["door_chain"] = result["door_chain"]
            witnesses.append(witness)
        routes.append(
            dict(
                route=route["key"],
                map_id=geometry["map_id"],
                classification=flow["status"],
                native_door_count=len(doors),
                native_internal_transport_count=len(
                    flow.get("native_internal_teleports", [])
                ),
                first_encounter_reachable_cell_count=flow.get(
                    "first_encounter_cell_count", 0
                ),
                exterior_exit_witnesses=witnesses,
                blocker=(
                    "missing_native_exterior_exit"
                    if not witnesses
                    else "native_internal_transport_graph_requires_exact_room_binding"
                    if flow.get("native_internal_teleports")
                    else "physical_room_graph_requires_review"
                    if not any(
                        w["physical_status"] == "physical_linear_chain_proved"
                        for w in witnesses
                    )
                    else "geometry_proved_roster_or_formation_pending"
                ),
            )
        )
    return dict(
        key=record["key"],
        name=record["name_es"],
        native_name=record["native"]["name_fr"],
        routes=routes,
        blocker="no_native_entry_route" if not routes else None,
    )


def main():
    inventory = json.loads(Path("docs/reports/dungeons/inventory.json").read_text())[
        "records"
    ]
    active = {
        r["key"]
        for r in json.loads(
            Path(
                "docs/reports/dungeons/MAXIMUM-ACTIVATION-BLOCKERS-20261010.json"
            ).read_text()
        )["records"]
        if r["status"] == "activated_native_flow"
    }
    active_names = {
        r["native"]["name_fr"] for r in inventory if r["key"] in active and ordinary(r)
    }
    flows = json.loads(
        Path(".runtime/local/all-native-dungeon-flows.json").read_text()
    )["records"]
    rows = [
        audit(
            r,
            [f for f in flows if f["key"] == r["key"]],
            Path(".runtime/local/all-native-dungeon-exploration"),
        )
        for r in inventory
        if ordinary(r) and r["native"]["name_fr"] not in active_names
    ]
    result = dict(
        schema_version=1,
        authority="Read-only exact native directed geometry; no inferred monster identities, fabricated coordinates or runtime writes",
        definitions=len(rows),
        distinct_native_names=len({r["native_name"] for r in rows}),
        route_blocker_counts=dict(
            Counter(q["blocker"] for r in rows for q in r["routes"])
        ),
        records=rows,
    )
    target = Path(
        "docs/reports/dungeons/REMAINING-CLASSIC-GEOMETRY-AUDIT-20261010.json"
    )
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "records"}))


if __name__ == "__main__":
    main()
