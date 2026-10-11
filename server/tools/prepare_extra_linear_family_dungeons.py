"""Resolve three omitted native physical routes with progressive family policy."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_native_branch_spine import build
from extract_native_door_flow import shortest_path
from extract_dungeon_family_bosses import load_role_catalog
from prepare_family_linear_dungeons import (
    audit_configuration_progression,
    progressive_configuration,
)
from prepare_native_physical_candidates import bind_exits
from validate_dungeon_flow_rosters import validate
from validate_prepared_physical_flows import validate as sequence


def main():
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
    audit = {
        r["key"]: r
        for r in load(
            "docs/reports/dungeons/REMAINING-CLASSIC-GEOMETRY-AUDIT-20261010.json"
        )["records"]
    }
    transports = load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    catalog = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    output = Path(".runtime/local/extra-linear-progressive-v5-20261010")
    output.mkdir(exist_ok=True)
    rows = []
    for identity in (84, 143, 74):
        key = f"native:{identity}"
        native, flow, boss = inventory[key], flows[key], evidence[key]
        row = dict(
            key=key, name=native["name_es"], route=flow["route"]["key"], attempts=[]
        )
        try:
            geometry = load(
                f'.runtime/local/all-native-dungeon-exploration/exploration-{flow["route"]["start_map_id"]}.json'
            )
            doors = [
                o
                for o in native["native_objects"]
                if o["type"] == "Door" and o["map_id"] == geometry["map_id"]
            ]
            topologies = []
            for route in audit[key]["routes"]:
                for witness in route["exterior_exit_witnesses"]:
                    try:
                        topology = build(
                            geometry, doors, flow["entry"], witness["exit_position"]
                        )
                        topology["physical_exit_objects"] = bind_exits(
                            topology, flow["route"], transports
                        )
                        topologies.append(topology)
                    except ValueError as error:
                        row["attempts"].append(
                            dict(exit=witness["exit_position"], reason=str(error))
                        )
            if not topologies:
                raise ValueError("No complete retained-native-topology exit contract")
            topology = max(topologies, key=lambda t: len(t["rooms"]))
            p = published_geometry(geometry["map_id"])
            combat = dict(map_id=p.map_id, cells=list(p.cells), edges=list(p.edges))
            attempts = []
            for capacity in (8, 6, 4, 3, 2, 1):
                try:
                    config = progressive_configuration(
                        dict(route=flow["route"], topology=topology, version=4),
                        native,
                        boss["boss_references"],
                        catalog,
                        capacity=capacity,
                        exclude=boss.get("excluded_nonfamily_references", []),
                        version=5,
                    )
                    placement = validate(
                        config, geometry, combat, enemy_formation, entry=flow["entry"]
                    )
                    if placement["status"] != "candidate_validated":
                        raise ValueError(json.dumps(placement["reasons"]))
                    proof = topology["local_mainspine_evidence"]
                    groups = proof.get(
                        "mandatory_gate_groups",
                        [[g] for g in proof["mandatory_gate_ids"]],
                    )
                    stages = []
                    for index, gate in enumerate(proof["mandatory_gate_ids"]):
                        position = next(
                            d["position"]
                            for d in topology["physical_doors"]
                            if d["source_id"] == gate
                        )
                        later = {g for group in groups[index + 1 :] for g in group}
                        blocked = [
                            d["position"]
                            for d in topology["physical_doors"]
                            if d["source_id"] in later
                        ]
                        stages.append(
                            dict(
                                directed_boundary_path=shortest_path(
                                    geometry["edges"], flow["entry"], position, blocked
                                )
                            )
                        )
                    traversal = sequence(
                        config, dict(entry=flow["entry"], stages=stages), placement
                    )
                    break
                except ValueError as error:
                    attempts.append(dict(capacity=capacity, reason=str(error)))
            else:
                raise ValueError(
                    "No strict progressive reachable six-player encounter: "
                    + json.dumps(attempts)
                )
            path = output / (row["route"] + ".json")
            if path.exists() and load(path) != config:
                raise ValueError(
                    "Refusing to overwrite immutable progressive candidate"
                )
            path.write_text(json.dumps(config, indent=2) + "\n")
            row.update(
                status="offline_configuration_prepared",
                path=str(path),
                rooms=len(topology["rooms"]),
                boss_references=boss["boss_references"],
                placement_validation=placement,
                sequence_validation=traversal,
                progression_validation=audit_configuration_progression(config, catalog),
                formation_reductions=attempts,
            )
        except (ValueError, KeyError) as error:
            row.update(status="blocked", reason=str(error))
        rows.append(row)
    Path(
        "docs/reports/dungeons/EXTRA-LINEAR-PROGRESSIVE-CANDIDATES-V5-20261010.json"
    ).write_text(
        json.dumps(
            dict(
                scope="Source-only retained native geometry; no activation",
                records=rows,
            ),
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            [
                dict(
                    name=r["name"],
                    status=r["status"],
                    reason=r.get("reason"),
                    attempts=r["attempts"],
                )
                for r in rows
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
