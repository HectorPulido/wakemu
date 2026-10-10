"""Separate evidence for DEV native flow activation from complete boss gameplay."""
import argparse
import json
from pathlib import Path


def audit(candidates, compositions, bosses, economy=None, activation=None):
    rosters = {r["route"]: r for r in compositions["records"]}
    abilities = {r["route"]: r for r in bosses["records"]}
    economy_rows = {r["route"]: r for r in (economy or {}).get("records", [])}
    activation_rows = (
        {r["route"]: r for r in (activation or {}).get("actions", [])}
        if (activation or {}).get("applied")
        else {}
    )
    rows = []
    for candidate in candidates["records"]:
        if candidate["status"] != "offline_configuration_prepared":
            continue
        route = candidate["route"]
        roster = rosters.get(route, {})
        boss = abilities.get(route, {})
        placement = roster.get("placement_validation", {})
        valid_placement = (
            isinstance(placement, dict)
            and placement.get("status") == "candidate_validated"
        )
        covered = [
            spell
            for b in boss.get("bosses", [])
            for spell in b["spells"]
            if spell["status"] == "catalog_roots_present"
        ]
        total = sum(len(b["spells"]) for b in boss.get("bosses", []))
        all_covered = bool(total) and len(covered) == total
        rows.append(
            dict(
                route=route,
                name=candidate["name"],
                configuration=candidate["path"],
                roster_identity_and_formation_validated=valid_placement,
                native_exterior_exits_bound=bool(candidate.get("exits")),
                covered_boss_owned_spells=len(covered),
                total_boss_owned_spells=total,
                boss_ability_catalog_complete=all_covered,
                full_boss_mechanics_verified=False,
                flow_activation_scope="explicit_dev_entry_spawn_victory_gates_exit_only",
                runtime_activation=activation_rows.get(route, {}).get(
                    "status", "not_performed"
                ),
                runtime_activation_evidence=activation_rows.get(route),
                actual_reward_settlement_evidence=economy_rows.get(route),
                pending_gates=(
                    []
                    if economy_rows.get(route, {}).get("status")
                    == "isolated_postgres_lifecycle_and_economy_passed"
                    else ["actual_reward_settlement_validation"]
                )
                + ["shared_complete_build_validation"],
                full_gameplay_blockers=["owned_boss_spell_catalog_incomplete"]
                if not all_covered
                else ["special_boss_mechanics_not_verified"],
                boss_details=boss.get("bosses", []),
            )
        )
    return dict(
        schema_version=1,
        scope="Readiness evidence only; no runtime activation",
        records=rows,
        limits="Flow can be accepted separately using authoritative finished fights. Missing boss abilities cannot be replaced by invented damage, spell ownership or claimed official AI.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-COMPLETE-CANDIDATES.json"),
    )
    parser.add_argument(
        "--compositions",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-COMPOSITION-COVERAGE.json"),
    )
    parser.add_argument(
        "--bosses",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-BOSS-ABILITY-COVERAGE.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-ACTIVATION-READINESS.json"),
    )
    parser.add_argument(
        "--economy",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-PG-LIFECYCLE-ECONOMY.json"),
    )
    parser.add_argument(
        "--activation",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-PHYSICAL-ACTIVATION.json"),
    )
    args = parser.parse_args()
    result = audit(
        *[
            json.loads(p.read_text())
            for p in (args.candidates, args.compositions, args.bosses)
        ],
        economy=json.loads(args.economy.read_text()) if args.economy.exists() else None,
        activation=json.loads(args.activation.read_text())
        if args.activation.exists()
        else None
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                candidates=len(result["records"]),
                full_boss_gameplay_ready=sum(
                    r["full_boss_mechanics_verified"] for r in result["records"]
                ),
            )
        )
    )


if __name__ == "__main__":
    main()
