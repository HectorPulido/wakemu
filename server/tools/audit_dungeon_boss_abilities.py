"""Audit native owned boss spell roots without claiming scripted mechanic parity."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def inspect_boss(monster, casting, effect_roots):
    spells = []
    for ability in monster.get("native_abilities", []):
        spell = ability["spell_id"]
        level = (
            monster["min_level"]
            if ability["level_parameter"] == -1
            else ability["level_parameter"]
        )
        record = casting.get(str(spell))
        reasons, roots, missing_roots = [], [], []
        if (
            record is None
            or type(level) is not int
            or not 1 <= level <= len(record["levels"])
        ):
            reasons.append("native_casting_level_unavailable")
        else:
            roots = record["levels"][level - 1][2]
            missing_roots = [root for root in roots if str(root) not in effect_roots]
            if missing_roots:
                reasons.append("owned_spell_root_not_in_compiled_npc_catalog")
        spells.append(
            dict(
                spell_id=spell,
                spell_level=level,
                roots=roots,
                missing_roots=missing_roots,
                status="catalog_roots_present" if not reasons else "unsupported",
                reasons=reasons,
            )
        )
    return dict(
        ref_id=monster["ref"],
        name=monster["name"],
        level=monster["min_level"],
        spells=spells,
        owned_root_coverage="all_present"
        if spells and all(s["status"] == "catalog_roots_present" for s in spells)
        else "incomplete",
        special_mechanic_validation="not_proved",
        limits="Root presence does not prove effect branches, AI, invulnerability phases, summons, victory or reward mechanics.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compositions",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-COMPOSITION-COVERAGE.json"),
    )
    parser.add_argument(
        "--monsters",
        type=Path,
        default=Path(
            ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/monsters.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-BOSS-ABILITY-COVERAGE.json"),
    )
    args = parser.parse_args()
    from wakfu_server.combat_npc_attack import npc_runtime_catalog
    from wakfu_server.combat_native_spell_casting import catalog

    compiled = npc_runtime_catalog()
    casting = catalog()
    monsters = {m["ref"]: m for m in json.loads(args.monsters.read_text())["monsters"]}
    rows = []
    for row in json.loads(args.compositions.read_text())["records"]:
        if row["status"] == "roster_candidate_prepared":
            rows.append(
                dict(
                    route=row["route"],
                    name=row["name"],
                    bosses=[
                        inspect_boss(monsters[ref], casting, compiled.effects)
                        for ref in row["boss_references"]
                    ],
                )
            )
    result = dict(
        schema_version=1,
        scope="Offline native owned ability catalog coverage, no combat modifications",
        records=rows,
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {r["route"]: [b["owned_root_coverage"] for b in r["bosses"]] for r in rows}
        )
    )


if __name__ == "__main__":
    main()
