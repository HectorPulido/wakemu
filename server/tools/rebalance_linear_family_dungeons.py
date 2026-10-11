"""Write fresh progressive, native-role-filtered linear dungeon candidates."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_dungeon_family_bosses import load_role_catalog
from prepare_family_linear_dungeons import (
    audit_configuration_progression,
    progressive_configuration,
    teleport_sequence,
)
from validate_dungeon_flow_rosters import validate
from validate_prepared_physical_flows import validate as physical_sequence


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
    catalog = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    flows = {
        r["route"]["key"]: r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
    }
    source = load("docs/reports/dungeons/FAMILY-LINEAR-CANDIDATES-20261010.json")[
        "records"
    ]
    output = Path(".runtime/local/family-linear-progressive-v5-20261010")
    output.mkdir(exist_ok=True)
    records = []
    for previous in source:
        if previous["status"] != "offline_configuration_prepared":
            continue
        row = {k: previous[k] for k in ("key", "name", "route")}
        attempts = []
        try:
            original = load(previous["path"])
            native, boss = inventory[row["key"]], evidence[row["key"]]
            flow = flows[row["route"]]
            geometry = original["topology"]["exploration_geometry"]
            p = published_geometry(original["topology"]["asset_map_id"])
            combat = dict(map_id=p.map_id, cells=list(p.cells), edges=list(p.edges))
            for capacity in (8, 6, 4, 3, 2, 1):
                try:
                    config = progressive_configuration(
                        original,
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
                    traversal = (
                        teleport_sequence(config, placement)
                        if config["topology"]["policy"]
                        == "native_teleport_victory_policy"
                        else physical_sequence(
                            config, flow["directed_physical_flows"][0], placement
                        )
                    )
                    break
                except ValueError as error:
                    attempts.append(dict(capacity=capacity, reason=str(error)))
            else:
                raise ValueError(
                    "No strict native-role-filtered composition with six-player formation: "
                    + json.dumps(attempts)
                )
            path = output / (row["route"] + ".json")
            if path.exists() and load(path) != config:
                raise ValueError(
                    "Refusing to overwrite an immutable progressive candidate"
                )
            path.write_text(json.dumps(config, indent=2) + "\n")
            row.update(
                status="offline_configuration_prepared",
                path=str(path),
                rooms=len(config["topology"]["rooms"]),
                boss_references=boss["boss_references"],
                placement_validation=placement,
                sequence_validation=traversal,
                progression_validation=audit_configuration_progression(config, catalog),
                formation_reductions=attempts,
            )
        except (KeyError, ValueError) as error:
            row.update(status="blocked", reason=str(error))
        records.append(row)
    report = dict(
        scope="Source-only progressive V5 candidates; frozen previous configurations preserved",
        records=records,
    )
    Path(
        "docs/reports/dungeons/FAMILY-LINEAR-PROGRESSIVE-CANDIDATES-V5-20261010.json"
    ).write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            [
                dict(name=r["name"], status=r["status"], reason=r.get("reason"))
                for r in records
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
