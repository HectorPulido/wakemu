#!/usr/bin/env python3
"""Generate evidence-backed candidates for unmodified dungeon victories.

Boss-and-dungeon predicates are explicit; names are client localization, not
proof of server quest-giver or additional cinematic execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
COMPLETE = re.compile(r"^Terminar la mazmorra (.+?)[.!]?$", re.I)
BOSS = re.compile(r"^Vencer (?:a la |al |a )(.+?) en la mazmorra (.+?)[.!]?$", re.I)
BOSS_NAMED = re.compile(
    r"^Vencer (?:a la |al |a )(.+?), jefe de la mazmorra (.+?)[.!]?$", re.I
)
NATIVE_CRITERION = re.compile(
    r"(?:GetRealLevel\(\)\s*>=\s*[1-9][0-9]*(?:\s+and\s+IsAchievement(?:Objective)?Complete\([1-9][0-9]*\))?|IsAchievement(?:Objective)?Complete\([1-9][0-9]*\))"
)


def build(definitions, candidates, language, monster_ids, revision):
    names = {}
    for line in language.decode("utf8").splitlines():
        k, sep, v = line.partition("=")
        if sep and k.startswith("content.137.") and k[12:].isdigit() and v:
            key = re.sub(r"^Mazmorra\s+", "", v, flags=re.I).casefold()
            names.setdefault(key, []).append(int(k[12:]))
    native = {x["d"]: x for x in definitions["definitions"]}
    out, excluded = [], []
    for row in candidates["candidates"]:
        q = native[row["definition_id"]]
        text = row["objective_es"]
        complete = COMPLETE.fullmatch(text)
        boss = BOSS.fullmatch(text) or BOSS_NAMED.fullmatch(text)
        # Native final-room roster identifies 1259 as Tofullero's boss.
        tofuhouse_boss = (
            q["d"] == 2138 and text == "Vencer al jefe de la mazmorra Tofullero"
        )
        if tofuhouse_boss:

            class ExplicitBoss:
                def group(self, index):
                    return "Tofu Real" if index == 1 else "Tofullero"

            boss = ExplicitBoss()
        reason = None
        if not complete and not boss:
            reason = "objective is not an exact victory or named boss sentence"
        elif len(q["cjJ"]) != 1 or q["cjU"] or q["cjL"] or q.get("getDuration"):
            reason = "multi-objective, periodic or timed"
        elif q["aqb"] is not False or q["aHe"] != f"IsAchievementActive({q['d']})":
            reason = "unsupported native flags or visibility"
        elif q["cjI"] and not NATIVE_CRITERION.fullmatch(q["cjI"].strip()):
            reason = "unsupported activation criterion"
        elif q["cjJ"][0]["ckc"] or q["cjJ"][0]["cke"] or q["cjJ"][0]["ckf"]:
            reason = "objective criterion or native variable dependency"
        elif any(r["aeV"] not in (5, 6, 11) for r in q["cjK"]):
            reason = "unsupported reward type"
        if reason:
            excluded.append(
                {
                    "quest_id": q["d"],
                    "objective_id": row["objective_id"],
                    "reason": reason,
                }
            )
            continue
        destination_name = (
            (complete.group(1) if complete else boss.group(2)).strip().rstrip(".!")
        )
        matches = names.get(
            re.sub(r"^Mazmorra\s+", "", destination_name, flags=re.I).casefold(), []
        )
        if len(matches) != 1:
            excluded.append(
                {
                    "quest_id": q["d"],
                    "objective_id": row["objective_id"],
                    "reason": "unknown or ambiguous native dungeon name",
                }
            )
            continue
        dungeon_id = matches[0]
        binding = {
            "quest_id": q["d"],
            "objective_id": row["objective_id"],
            "count": 1,
            "kind": "dungeon",
            "target_id": dungeon_id,
            "evidence": "Reconstructed: exact native dungeon title in localized objective; initial acceptance on victory is local policy.",
        }
        if boss:
            boss_name = boss.group(1).casefold()
            native_boss = []
            # Client content.7 names need exact unique comparison, with optional
            # grammatical article removed from target localization.
            for line in language.decode("utf8").splitlines():
                k, sep, v = line.partition("=")
                if (
                    sep
                    and k.startswith("content.7.")
                    and k[10:].isdigit()
                    and v.casefold() == boss_name
                ):
                    native_boss.append(int(k[10:]))
            if len(native_boss) != 1 or native_boss[0] not in monster_ids:
                excluded.append(
                    {
                        "quest_id": q["d"],
                        "objective_id": row["objective_id"],
                        "reason": "unknown or ambiguous native boss reference",
                    }
                )
                continue
            binding.update(
                kind="boss",
                target_id=native_boss[0],
                dungeon_id=dungeon_id,
                evidence="Reconstructed: exact boss and dungeon names in client; objective requires both. Initial acceptance on victory is local policy.",
            )
        out.append(binding)
    return {
        "schema": "combat_mission_bindings_v1",
        "revision": revision,
        "bindings": sorted(out, key=lambda x: x["quest_id"]),
    }, excluded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--definitions",
        type=Path,
        default=ROOT / ".runtime/quest-extraction/native-quest-definitions.json",
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=ROOT / ".runtime/quest-reconstruction/combat-quest-candidates.json",
    )
    parser.add_argument(
        "--language", type=Path, default=ROOT / "client/contents/i18n/i18n_es.jar"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime/quest-reconstruction/dungeon-combat-bindings.json",
    )
    parser.add_argument(
        "--exclusions",
        type=Path,
        default=ROOT / ".runtime/quest-reconstruction/dungeon-combat-exclusions.json",
    )
    args = parser.parse_args()
    raw = args.definitions.read_bytes()
    with zipfile.ZipFile(args.language) as z:
        language = z.read("texts_es.properties")
    from wakfu_server import monsters

    data, excluded = build(
        json.loads(raw),
        json.loads(args.candidates.read_text()),
        language,
        set(monsters.REFERENCES),
        hashlib.sha256(raw).hexdigest(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    args.exclusions.write_text(
        json.dumps(excluded, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"{len(data['bindings'])} reconstructed bindings; {len(excluded)} excluded")


if __name__ == "__main__":
    main()
