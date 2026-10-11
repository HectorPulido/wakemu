"""Prepare local family encounters on retained native mandatory-gate branch stages."""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_native_branch_spine import build, deepest_native_stage, shortest_path
from native_family_configuration_base import base
from prepare_family_linear_dungeons import family_roster
from prepare_native_physical_candidates import bind_exits
from validate_dungeon_flow_rosters import validate
from validate_prepared_physical_flows import validate as sequence


def main():
    from wakfu_server.dungeon_runtime_config import prepare_configuration
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    load = lambda p: json.loads(Path(p).read_text())
    native = {
        r["key"]: r for r in load("docs/reports/dungeons/inventory.json")["records"]
    }
    flows = {
        r["route"]["key"]: r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
    }
    evidence = {
        r["key"]: r
        for r in load("docs/reports/dungeons/REMAINING-FAMILY-BOSSES-20261010.json")[
            "records"
        ]
    }
    source = load(
        "docs/reports/dungeons/REMAINING-CLASSIC-GEOMETRY-AUDIT-20261010.json"
    )["records"]
    transports = load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    output = Path(".runtime/local/family-branch-candidates-v2-20261010")
    output.mkdir(exist_ok=True)
    rows = []
    for record in source:
        for route in record["routes"]:
            if route["blocker"] != "physical_room_graph_requires_review":
                continue
            key = record["key"]
            n = native[key]
            flow = flows[route["route"]]
            row = dict(key=key, name=n["name_es"], route=route["route"])
            failures = []
            try:
                bosses = evidence[key].get("boss_references", [])
                if len(bosses) != 1:
                    raise ValueError(
                        "Exactly one identified native family boss required for this preparer"
                    )
                geometry = load(
                    f".runtime/local/all-native-dungeon-exploration/exploration-{route['map_id']}.json"
                )
                doors = [
                    o
                    for o in n["native_objects"]
                    if o["map_id"] == route["map_id"] and o["type"] == "Door"
                ]
                candidates = []
                for exit_witness in route["exterior_exit_witnesses"]:
                    try:
                        candidates.append(
                            build(
                                geometry,
                                doors,
                                flow["entry"],
                                exit_witness["exit_position"],
                            )
                        )
                    except ValueError as error:
                        failures.append(str(error))
                if not candidates:
                    candidates.append(
                        deepest_native_stage(geometry, doors, flow["entry"])
                    )
                topology = max(candidates, key=lambda t: len(t["rooms"]))
                topology["physical_exit_objects"] = bind_exits(
                    topology, flow["route"], transports, allow_physical_return=True
                )
                p = published_geometry(route["map_id"])
                combat = dict(map_id=p.map_id, cells=list(p.cells), edges=list(p.edges))
                attempts = []
                for quantity in (8, 6, 4, 3, 2, 1):
                    roster = family_roster(
                        n,
                        len(topology["rooms"]),
                        bosses[0],
                        quantity=quantity,
                        exclude=evidence[key].get("excluded_nonfamily_references", []),
                    )
                    compiled = base(n, flow["route"], roster["rooms"])
                    config = prepare_configuration(
                        compiled["compiled_plan"],
                        copy.deepcopy(topology),
                        flow["route"],
                        version=4,
                        provenance=topology["progression_authority"],
                    )
                    placement = validate(
                        config, geometry, combat, enemy_formation, entry=flow["entry"]
                    )
                    if placement["status"] != "candidate_validated":
                        attempts.append(
                            dict(quantity=quantity, reasons=placement["reasons"])
                        )
                        continue
                    stages = []
                    for gate in topology["local_mainspine_evidence"][
                        "mandatory_gate_ids"
                    ]:
                        position = next(
                            d["position"]
                            for d in topology["physical_doors"]
                            if d["source_id"] == gate
                        )
                        later = {
                            gate
                            for group in topology["local_mainspine_evidence"][
                                "mandatory_gate_groups"
                            ][len(stages) + 1 :]
                            for gate in group
                        }
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
                    try:
                        traversal = sequence(
                            config, dict(entry=flow["entry"], stages=stages), placement
                        )
                    except ValueError as error:
                        attempts.append(dict(quantity=quantity, reasons=[str(error)]))
                        continue
                    break
                else:
                    raise ValueError(
                        "No complete six-player formation/sequence: "
                        + json.dumps(attempts)
                    )
                path = output / (route["route"] + ".json")
                path.write_text(json.dumps(config, indent=2) + "\n")
                row.update(
                    status="offline_configuration_prepared",
                    path=str(path),
                    rooms=len(topology["rooms"]),
                    boss_references=bosses,
                    local_quantity=quantity,
                    formation_reductions=attempts,
                    placement_validation=placement,
                    sequence_validation=traversal,
                )
            except (ValueError, KeyError) as error:
                row.update(status="blocked", reason=str(error))
            rows.append(row)
    target = Path("docs/reports/dungeons/FAMILY-BRANCH-CANDIDATES-V2-20261010.json")
    target.write_text(
        json.dumps(
            dict(
                scope="Source-only local family branch stages; all native terrain/gates retained; no runtime writes",
                records=rows,
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(
        json.dumps(
            [
                dict(name=r["name"], status=r["status"], reason=r.get("reason"))
                for r in rows
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
