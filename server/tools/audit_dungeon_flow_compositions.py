"""Join native flow candidates to reviewed roster evidence without activation."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.dungeon_local_roster_policy import draft


def audit(
    inventory,
    flows,
    candidate_dir,
    validate_placement=False,
    native_room_policy=False,
    boss_identity_evidence=None,
):
    indexed = {r["key"]: r for r in inventory["records"]}
    identities = {
        r["key"]: r for r in (boss_identity_evidence or {}).get("records", [])
    }
    output = []
    for flow in flows["records"]:
        record = indexed[flow["key"]]
        row = dict(
            key=record["key"],
            name=record["name_es"],
            route=flow["route"]["key"],
            flow_status=flow["status"],
        )
        reasons = []
        candidate_path = Path(candidate_dir) / (row["route"] + ".json")
        if (
            flow["status"]
            not in (
                "physical_linear_chain_proved",
                "native_teleport_linear_chain_proved",
            )
            or not candidate_path.exists()
        ):
            reasons.append("native_linear_physical_flow_not_proved")
        else:
            topology = json.loads(candidate_path.read_text())
            count = len(topology["rooms"])
            row["native_physical_rooms"] = count
            guide = next((g for g in record["guides"] if g["rooms"]), None)
            known = guide["rooms"] if guide else []
            bosses = {
                m["ref_id"]
                for r in known
                for m in r["monsters"]
                if m.get("role") == "boss" and m.get("ref_id")
            }
            # Tofu identity was explicitly reviewed against its native species pool.
            if record["key"] == "native:27":
                bosses.add(1259)
            pool = record["native_species_pool"]
            identity = identities.get(record["key"], {})
            if identity.get("status") == "exact_native_name_in_boss_heading":
                pool_refs = {m["ref_id"] for m in pool}
                reviewed = identity.get("boss_references", [])
                if len(reviewed) == 1 and reviewed[0] in pool_refs:
                    bosses.update(reviewed)
                    row["boss_identity_evidence"] = identity
            if record["native"]["type"] == "ULTIMATE_BOSS" and len(pool) == 1:
                bosses.add(pool[0]["ref_id"])
            row["boss_references"] = sorted(bosses)
            if known and len(known) != count:
                if native_room_policy:
                    row["unaltered_guide_rooms"] = known
                    row[
                        "room_adaptation_authority"
                    ] = "Explicit DEV native region count; guide room assignment not reused"
                    known = []
                else:
                    reasons.append(
                        "reviewed_guide_room_count_differs_from_native_physical_regions"
                    )
            if not bosses:
                reasons.append("final_boss_identity_not_reviewed")
            if not reasons:
                catalog = [
                    dict(
                        ref=m["ref_id"],
                        name=m["name_es"],
                        min_level=m["min_level"],
                        max_level=m["max_level"],
                    )
                    for m in pool
                ]
                try:
                    roster = draft(
                        dict(
                            slug=row["route"],
                            definition_id=record["native"]["id"],
                            rooms=known,
                        ),
                        record["native"],
                        catalog,
                        room_count=count,
                        boss_references=sorted(bosses),
                    )
                    if any(
                        type(m.get("ref_id")) is not int or m["ref_id"] <= 0
                        for room in roster["rooms"]
                        for m in room["monsters"]
                    ):
                        raise ValueError(
                            "Reviewed roster contains unresolved native monster identities"
                        )
                    row["roster_candidate"] = roster
                    row[
                        "composition_authority"
                    ] = "Preserved reviewed quantities; missing slots use explicit DEV policy"
                except ValueError as error:
                    reasons.append("roster_policy_refused: " + str(error))
            row[
                "placement_validation"
            ] = "requires_exported_combat_profile_and_existing_formation_validator"
            row["exit_validation"] = "requires_native_exit_object_binding"
            if validate_placement and "roster_candidate" in row:
                from wakfu_server.combat_geometry import published_geometry
                from wakfu_server.dungeon_encounters import enemy_formation
                from validate_dungeon_flow_rosters import validate

                try:
                    combat = published_geometry(topology["asset_map_id"])
                    combat = dict(
                        map_id=combat.map_id,
                        cells=list(combat.cells),
                        edges=list(combat.edges),
                    )
                    configuration = dict(
                        topology=topology,
                        compiled_plan=dict(
                            rooms=row["roster_candidate"]["rooms"],
                            official=False,
                            boss_references=sorted(bosses),
                            generated_fields=[
                                dict(
                                    order=r["order"], policy_applied=r["policy_applied"]
                                )
                                for r in row["roster_candidate"]["rooms"]
                            ],
                        ),
                    )
                    row["placement_validation"] = validate(
                        configuration,
                        topology["exploration_geometry"],
                        combat,
                        enemy_formation,
                        entry=flow["entry"],
                    )
                    if row["placement_validation"]["status"] != "candidate_validated":
                        reasons.append("native_formation_validation_failed")
                except ValueError as error:
                    row["placement_validation"] = str(error)
                    reasons.append("native_combat_geometry_unavailable")
        row["status"] = (
            "manual_evidence_required" if reasons else "roster_candidate_prepared"
        )
        row["reasons"] = reasons
        output.append(row)
    return dict(
        schema_version=1,
        scope="Offline evidence audit; no configurations activated",
        counts=dict(Counter(r["status"] for r in output)),
        reasons=dict(Counter(reason for r in output for reason in r["reasons"])),
        records=output,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory", type=Path, default=Path("docs/reports/dungeons/inventory.json")
    )
    parser.add_argument(
        "--flows",
        type=Path,
        default=Path(".runtime/local/all-native-dungeon-flows.json"),
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path(".runtime/local/native-physical-topology-candidates"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-COMPOSITION-COVERAGE.json"),
    )
    parser.add_argument("--validate-placement", action="store_true")
    parser.add_argument("--native-room-policy", action="store_true")
    parser.add_argument("--boss-identities", type=Path)
    args = parser.parse_args()
    result = audit(
        json.loads(args.inventory.read_text()),
        json.loads(args.flows.read_text()),
        args.candidates,
        args.validate_placement,
        args.native_room_policy,
        json.loads(args.boss_identities.read_text()) if args.boss_identities else None,
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            dict(counts=result["counts"], reasons=result["reasons"]), ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
