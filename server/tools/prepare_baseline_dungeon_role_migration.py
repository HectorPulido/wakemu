"""Prepare source-only replacements for the frozen active47 dungeon baseline."""
import json
import copy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_dungeon_family_bosses import identify, load_role_catalog, native_role
from prepare_family_linear_dungeons import (
    progressive_configuration,
    teleport_sequence,
    audit_configuration_progression,
)
from validate_dungeon_flow_rosters import validate
from validate_prepared_physical_flows import validate as physical_sequence


def main():
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    load = lambda path: json.loads(Path(path).read_text())
    source = load(".runtime/local/baseline47-configuration-export-20261010.json")
    inventory = {
        r["key"]: r for r in load("docs/reports/dungeons/inventory.json")["records"]
    }
    catalog = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    flows = {
        r["route"]["key"]: r
        for r in load(".runtime/local/all-native-dungeon-flows.json")["records"]
    }
    output = Path(".runtime/local/baseline47-role-progressive-v1-20261010")
    output.mkdir(exist_ok=True)
    records = []
    for row in source["records"]:
        route = row["route"]
        original = row["configuration"]
        native = inventory["native:" + route.split("_")[-1]]
        result = dict(
            route=route,
            name=native["name_es"],
            original_version=row["version"],
            original_sha256=row["configuration_sha256"],
        )
        if native["native"]["type"] == "ULTIMATE_BOSS":
            forbidden = [
                (m["ref_id"], native_role(catalog.get(m["ref_id"])))
                for room in original["compiled_plan"]["rooms"]
                for m in room["monsters"]
                if native_role(catalog.get(m["ref_id"]))
                in {"archmonster", "dominant", "unknown"}
            ]
            result.update(
                status="ultimate_boss_unchanged" if not forbidden else "blocked",
                forbidden_roles=forbidden,
                boss_flag_notes=[
                    m["ref_id"]
                    for room in original["compiled_plan"]["rooms"]
                    for m in room["monsters"]
                    if m.get("role") == "boss"
                    and native_role(catalog.get(m["ref_id"])) != "boss"
                ],
            )
            records.append(result)
            continue
        attempts = []
        try:
            evidence = identify(
                [catalog[m["ref_id"]] for m in native["native_species_pool"]]
            )
            if not evidence["boss_references"]:
                raise ValueError("No certified native family BOSS actor")
            flow = flows[route]
            published = published_geometry(original["topology"]["asset_map_id"])
            combat = dict(
                map_id=published.map_id,
                cells=list(published.cells),
                edges=list(published.edges),
            )
            for capacity in (8, 6, 4, 3, 2, 1):
                try:
                    config = progressive_configuration(
                        original,
                        native,
                        evidence["boss_references"],
                        catalog,
                        capacity=capacity,
                        exclude=evidence["excluded_nonfamily_references"],
                        version=original["version"] + 1,
                    )
                    placement = validate(
                        config,
                        original["topology"]["exploration_geometry"],
                        combat,
                        enemy_formation,
                        entry=flow["entry"],
                    )
                    if placement["status"] != "candidate_validated":
                        raise ValueError(json.dumps(placement["reasons"]))
                    if config["topology"]["policy"] == "native_teleport_victory_policy":
                        traversal = teleport_sequence(config, placement)
                    else:
                        validation_config = copy.deepcopy(config)
                        recovered = []
                        for exit_object in validation_config["topology"][
                            "physical_exit_objects"
                        ]:
                            if "native_approach_cells" in exit_object:
                                continue
                            obj = next(
                                v
                                for v in native["native_objects"]
                                if v["id"] == exit_object["source_id"]
                            )
                            native_exit = next(
                                v
                                for v in native["native_exits"]
                                if v["source_object"] == obj["id"]
                            )
                            if not any(
                                v.get("native_altitude_walkable")
                                for v in native_exit["destinations"]
                            ):
                                raise ValueError(
                                    "Exit has no verified native exterior arrival"
                                )
                            destinations = [
                                v
                                for v in native_exit["destinations"]
                                if v.get("native_altitude_walkable")
                            ]
                            if len(destinations) != 1:
                                raise ValueError(
                                    "Native exterior destination is ambiguous"
                                )
                            exit_object["destination"] = {
                                key: destinations[0][key]
                                for key in ("map_id", "x", "y", "z")
                            }
                            cells = next(
                                v["cells"]
                                for v in config["topology"]["rooms"]
                                if v["order"] == exit_object["room_order"]
                            )
                            approaches = [
                                p
                                for p in cells
                                if p[2] == obj["z"]
                                and abs(p[0] - obj["x"]) + abs(p[1] - obj["y"]) <= 1
                            ]
                            if not approaches:
                                raise ValueError(
                                    "Native exit has no cardinal source approach"
                                )
                            exit_object["native_approach_cells"] = approaches
                            recovered.append(
                                dict(
                                    source_id=obj["id"],
                                    native_approach_cells=approaches,
                                    evidence="installed native object coordinates and native exterior destinations",
                                )
                            )
                        directed = (
                            flow["directed_physical_flows"][0]
                            if flow["directed_physical_flows"]
                            else dict(entry=flow["entry"], stages=[])
                        )
                        traversal = physical_sequence(
                            validation_config, directed, placement
                        )
                        traversal["validation_only_recovered_exit_metadata"] = recovered
                    break
                except (KeyError, IndexError, ValueError) as error:
                    attempts.append(dict(capacity=capacity, reason=str(error)))
            else:
                raise ValueError(
                    "No complete source-only replacement: " + json.dumps(attempts)
                )
            if config["topology"] != original["topology"]:
                raise ValueError("Native topology changed during composition migration")
            path = output / (route + ".json")
            if path.exists() and load(path) != config:
                raise ValueError("Refusing to overwrite immutable candidate")
            path.write_text(json.dumps(config, indent=2) + "\n")
            result.update(
                status="offline_configuration_prepared",
                path=str(path),
                version=config["version"],
                boss_references=evidence["boss_references"],
                excluded_nonfamily_references=evidence["excluded_nonfamily_references"],
                placement_validation=placement,
                sequence_validation=traversal,
                progression_validation=audit_configuration_progression(config, catalog),
                capacity_reductions=attempts,
            )
        except (KeyError, IndexError, ValueError) as error:
            result.update(status="blocked", reason=str(error))
        records.append(result)
        print(route, result["status"], flush=True)
    report = dict(
        scope="Frozen47 active baseline remediation; source-only versioned candidates; zero runtime writes; original native geometry preserved",
        records=records,
    )
    Path(
        "docs/reports/dungeons/BASELINE47-ROLE-PROGRESSIVE-MIGRATION-20261010.json"
    ).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
