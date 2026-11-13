#!/usr/bin/env python3
"""Build conservative reconstructed kill bindings from client names and native monsters.

A literal one-target sentence is evidence for a candidate, not proof of the
original server's acceptance rules. The runtime's implicit-acceptance policy
is a local reconstruction; inspect the exclusion report before publication.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
STRICT = r"(?:Matar|Vencer|Derrotar|Eliminar)\s+(?:al|a la|a)\s+{}[.!]?"
CRITERION = re.compile(
    r"(?:GetRealLevel\(\)\s*>=\s*[1-9][0-9]*(?:\s+and\s+IsAchievementComplete\([1-9][0-9]*\))?|IsAchievementComplete\([1-9][0-9]*\))"
)


def build(definitions, candidates, monster_ids, revision):
    native = {row["d"]: row for row in definitions["definitions"]}
    accepted, excluded = [], []
    for row in candidates["candidates"]:
        quest = native[row["definition_id"]]
        hits = row["monster_name_matches"]
        reason = None
        if len(row["all_objective_ids"]) != 1:
            reason = "multiple objectives"
        elif (
            row["period_seconds"] or row["duration_seconds"] or quest.get("getDuration")
        ):
            reason = "recurring or timed"
        elif len(hits) != 1 or hits[0]["ambiguous_name"]:
            reason = "ambiguous monster name"
        elif not re.fullmatch(
            STRICT.format(re.escape(hits[0]["text"])), row["objective_es"], re.I
        ):
            reason = "additional objective wording or mode"
        elif hits[0]["reference_ids"][0] not in monster_ids:
            reason = "monster not in native creature catalog"
        elif (
            quest["aqb"] is not False
            or quest["cjO"] is not False
            or quest["cjW"] is not False
        ):
            reason = "unsupported native flags"
        elif quest["aHe"] != f"IsAchievementActive({quest['d']})":
            reason = "nonstandard native visibility criterion"
        elif quest["cjI"] and not CRITERION.fullmatch(quest["cjI"].strip()):
            reason = "unsupported activation criterion"
        elif any(row["objective_criteria"]) or quest["cjJ"][0]["ckf"]:
            reason = "objective criterion or native variable dependency"
        elif any(reward["aeV"] not in (5, 6, 11) for reward in quest["cjK"]):
            reason = "unsupported reward type"
        if reason:
            excluded.append(
                {
                    "quest_id": row["definition_id"],
                    "objective_id": row["objective_id"],
                    "reason": reason,
                }
            )
            continue
        accepted.append(
            {
                "quest_id": row["definition_id"],
                "objective_id": row["objective_id"],
                "kind": "monster",
                "target_id": hits[0]["reference_ids"][0],
                "count": 1,
                "evidence": "Reconstructed: objective text exactly names one unique native monster; initial acceptance on victory is local policy, not recovered native quest-giver behavior.",
            }
        )
    return {
        "schema": "combat_mission_bindings_v1",
        "revision": revision,
        "bindings": sorted(accepted, key=lambda row: row["quest_id"]),
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
        default=ROOT / ".runtime/quest-reconstruction/named-combat-objectives.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime/quest-reconstruction/named-combat-bindings.json",
    )
    parser.add_argument(
        "--exclusions",
        type=Path,
        default=ROOT / ".runtime/quest-reconstruction/named-combat-exclusions.json",
    )
    args = parser.parse_args()
    raw = args.definitions.read_bytes()
    from wakfu_server import monsters

    document, excluded = build(
        json.loads(raw),
        json.loads(args.candidates.read_text()),
        set(monsters.REFERENCES),
        hashlib.sha256(raw).hexdigest(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    args.exclusions.write_text(
        json.dumps(excluded, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f"{len(document['bindings'])} reconstructed bindings; {len(excluded)} excluded"
    )


if __name__ == "__main__":
    main()
