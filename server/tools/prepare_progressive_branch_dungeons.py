"""Prepare versioned role-filtered progressive encounters on frozen native branch stages."""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_dungeon_family_bosses import load_role_catalog, native_role
from native_family_configuration_base import base
from prepare_family_linear_dungeons import (
    progressive_family_roster,
    eligible_family_refs,
)
from validate_dungeon_flow_rosters import validate
from validate_prepared_physical_flows import validate as sequence
from extract_native_door_flow import shortest_path


def main():
    from wakfu_server.dungeon_runtime_config import prepare_configuration
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    load = lambda p: json.loads(Path(p).read_text())
    native = {
        r["key"]: r for r in load("docs/reports/dungeons/inventory.json")["records"]
    }
    roles_path = ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    roles = load_role_catalog(roles_path)
    identities = {
        r["key"]: r
        for r in load("docs/reports/dungeons/REMAINING-FAMILY-BOSSES-20261010.json")[
            "records"
        ]
    }
    sources = [
        "docs/reports/dungeons/FAMILY-BRANCH-CANDIDATES-V2-20261010.json",
        "docs/reports/dungeons/FAMILY-BRANCH-ANCHOR-CANDIDATES-V3-20261010.json",
    ]
    rows = []
    output = Path(".runtime/local/progressive-family-branch-candidates-v4-20261010")
    output.mkdir(exist_ok=True)
    for source in sources:
        for original in load(source)["records"]:
            if original["status"] != "offline_configuration_prepared":
                continue
            n = native[original["key"]]
            row = dict(
                key=n["key"],
                name=n["name_es"],
                route=original["route"],
                source_report=source,
                source_configuration=original["path"],
            )
            try:
                frozen = load(original["path"])
                topology = frozen["topology"]
                geometry = topology["exploration_geometry"]
                entry = topology["local_mainspine_evidence"]["entry"]
                route = frozen["route"]
                bosses = original["boss_references"]
                eligible = eligible_family_refs(n, roles, bosses) - set(
                    identities[n["key"]].get("excluded_nonfamily_references", [])
                )
                excluded = sorted(
                    {m["ref_id"] for m in n["native_species_pool"]} - eligible
                )
                p = published_geometry(topology["asset_map_id"])
                combat = dict(map_id=p.map_id, cells=list(p.cells), edges=list(p.edges))
                attempts = []
                capacities = sorted(
                    {c for c in (8, 6, 4, 3, 2, 1) if c <= original["local_quantity"]},
                    reverse=True,
                )
                for capacity in capacities:
                    try:
                        roster = progressive_family_roster(
                            n,
                            len(topology["rooms"]),
                            bosses,
                            capacity=capacity,
                            eligible_refs=eligible,
                        )
                        compiled = base(n, route, roster["rooms"])
                        compiled["compiled_plan"]["progression_policy"] = roster[
                            "progression_policy"
                        ]
                        compiled["compiled_plan"]["role_eligibility_evidence"] = dict(
                            source=roles_path,
                            excluded_references=excluded,
                            prohibited_roles=["dominant", "archmonster", "unknown"],
                        )
                        config = prepare_configuration(
                            compiled["compiled_plan"],
                            copy.deepcopy(topology),
                            route,
                            version=5,
                            provenance="User-authorized progressive native family encounters; native role exclusions; frozen native gate stage geometry",
                        )
                        placement = validate(
                            config, geometry, combat, enemy_formation, entry=entry
                        )
                        if placement["status"] != "candidate_validated":
                            attempts.append(
                                dict(capacity=capacity, reasons=placement["reasons"])
                            )
                            continue
                        stages = []
                        evidence = topology["local_mainspine_evidence"]
                        for gate in evidence["mandatory_gate_ids"]:
                            position = next(
                                d["position"]
                                for d in topology["physical_doors"]
                                if d["source_id"] == gate
                            )
                            later = {
                                gate
                                for group in evidence["mandatory_gate_groups"][
                                    len(stages) + 1 :
                                ]
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
                                        geometry["edges"], entry, position, blocked
                                    )
                                )
                            )
                        traversal = sequence(
                            config, dict(entry=entry, stages=stages), placement
                        )
                    except ValueError as error:
                        attempts.append(dict(capacity=capacity, reasons=[str(error)]))
                        continue
                    break
                else:
                    raise ValueError(
                        "No strict progression with six-player native formation: "
                        + json.dumps(attempts)
                    )
                path = output / (original["route"] + ".json")
                path.write_text(json.dumps(config, indent=2) + "\n")
                row.update(
                    status="offline_configuration_prepared",
                    path=str(path),
                    rooms=len(topology["rooms"]),
                    boss_references=bosses,
                    common_formation_capacity=capacity,
                    progression_policy=roster["progression_policy"],
                    excluded_references=excluded,
                    excluded_roles={
                        str(ref): native_role(roles.get(ref)) for ref in excluded
                    },
                    placement_validation=placement,
                    sequence_validation=traversal,
                    formation_reductions=attempts,
                )
            except (ValueError, KeyError) as error:
                row.update(status="blocked", reason=str(error))
            rows.append(row)
    report = dict(
        scope="Source-only progressive role-filtered local family encounters; V2/V3 unchanged; no activation",
        records=rows,
    )
    Path(
        "docs/reports/dungeons/PROGRESSIVE-FAMILY-BRANCH-CANDIDATES-V4-20261010.json"
    ).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            [
                dict(
                    name=r["name"],
                    status=r["status"],
                    reason=r.get("reason"),
                    progression=r.get("progression_policy", {}).get("rooms"),
                )
                for r in rows
            ],
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
