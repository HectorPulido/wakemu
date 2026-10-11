"""Prepare local family arenas on native open, separator-free components.

Read-only preparation. Composition is user-authorized approximation, while boss
identity, native membership, directed entry/exit and placement remain validated.
"""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_family_configuration_base import base
from prepare_open_boss_dungeons import prepare


def main():
    from extract_dungeon_family_bosses import load_role_catalog
    from prepare_family_linear_dungeons import (
        progressive_family_roster,
        eligible_family_refs,
    )
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
    roles = load_role_catalog(
        ".runtime/local/duel-core-final-context-20261007-r7/r4-check/app/protocol/monsters.json"
    )
    flows = load(".runtime/local/all-native-dungeon-flows.json")["records"]
    transports = load(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    output = Path(".runtime/local/family-open-candidates-v2-20261010")
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for flow in flows:
        if (
            flow["key"] not in evidence
            or flow["status"] != "open_geometry_no_separator"
        ):
            continue
        proof = evidence[flow["key"]]
        row = dict(key=flow["key"], route=flow["route"]["key"], name=flow["name"])
        try:
            native = copy.deepcopy(inventory[flow["key"]])
            bosses = proof["boss_references"]
            if (
                not native["native_species_pool"]
                and proof["status"] == "web_family_exact_native_names_and_boss_property"
            ):
                source = load(proof["evidence"]["source_path"])["monsters"]
                selected = set(bosses + proof["family_pool_references"])
                native["native_species_pool"] = [
                    dict(
                        ref_id=m["ref"],
                        name_es=m["name"],
                        min_level=m["min_level"],
                        max_level=m["max_level"],
                    )
                    for m in source
                    if m["ref"] in selected and m["family_id"] in proof["family_ids"]
                ]
            pool = {m["ref_id"]: m for m in native["native_species_pool"]}
            regular = proof["family_pool_references"]
            if not bosses or any(ref not in pool for ref in bosses + regular):
                raise ValueError("Evidence roster is outside native dungeon membership")
            eligible = eligible_family_refs(native, roles, bosses)
            roster = progressive_family_roster(
                native,
                1,
                bosses,
                capacity=8,
                eligible_refs=eligible,
                exclude=proof.get("excluded_nonfamily_references", []),
            )
            monsters = roster["rooms"][0]["monsters"]
            compiled = base(native, flow["route"], [dict(order=1, monsters=monsters)])
            # Multi-room guides cannot prove inaccessible stages in a separator-free
            # component. Preserve their evidence but explicitly use one local arena.
            native["guides"] = []
            mid = flow["route"]["start_map_id"]
            geometry = load(
                f".runtime/local/all-native-dungeon-exploration/exploration-{mid}.json"
            )
            published = published_geometry(mid)
            combat = dict(
                map_id=mid, cells=list(published.cells), edges=list(published.edges)
            )
            config, placement, sequence = prepare(
                native,
                flow,
                compiled,
                geometry,
                transports,
                combat,
                enemy_formation,
                reviewed_roster=monsters,
            )
            config[
                "provenance"
            ] = "User-authorized local family arena; native family boss identity and ordinary members; official room structure and quantities not claimed; directed entry and native exit validated"
            config["compiled_plan"]["roster_policy_evidence"] = proof
            config["compiled_plan"][
                "policy_mode"
            ] = "user_authorized_role_filtered_single_family_arena"
            config["compiled_plan"]["progression_policy"] = roster["progression_policy"]
            config["version"] = 6
            config["context_policy"]["policy_version"] = 6
            from wakfu_server.maps.dungeon_runtime_config import canonical_hash

            config["evidence_hashes"]["plan"] = canonical_hash(config["compiled_plan"])
            path = output / (row["route"] + ".json")
            path.write_text(json.dumps(config, indent=2) + "\n")
            row.update(
                status="offline_configuration_prepared",
                path=str(path),
                rooms=1,
                boss_references=bosses,
                excluded_native_roles=sorted(set(pool) - eligible),
                progression_policy=roster["progression_policy"],
                placement_validation=placement,
                sequence_validation=sequence,
                local_policy="One local open arena; eight family actors including each identified boss once; official multi-room progression not claimed",
            )
        except (ValueError, KeyError, StopIteration, FileNotFoundError) as error:
            row.update(status="blocked", reason=str(error) or type(error).__name__)
        records.append(row)
    Path("docs/reports/dungeons/FAMILY-OPEN-CANDIDATES-V2-20261010.json").write_text(
        json.dumps(dict(records=records), indent=2) + "\n"
    )
    print(
        json.dumps(
            [(r["name"], r["status"], r.get("reason")) for r in records],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
