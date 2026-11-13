#!/usr/bin/env python3
"""Join native quest definitions and literal dialogue references without inferring transitions."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build(definitions, references):
    texts = definitions["translations"]
    reward_types = {x["id"]: x["name"] for x in definitions["reward_types"]}
    by_quest, by_objective = {}, {}
    for ref in references["references"]:
        target = by_quest if ref["kind"] == "achievement" else by_objective
        target.setdefault(ref["id"], []).append(ref)

    def localized(category, identity):
        key = f"content.{category}.{identity}"
        return {lang: table[key] for lang, table in texts.items() if key in table}

    result = []
    for row in definitions["definitions"]:
        quest_id = row["d"]
        objectives = []
        for obj in row["cjJ"]:
            objectives.append(
                {
                    "id": obj["d"],
                    "text": localized(64, obj["d"]),
                    "native": obj,
                    "dialogue_references": by_objective.get(obj["d"], []),
                }
            )
        rewards = [
            {
                "type": reward_types.get(r["aeV"]),
                "native": r,
                "emote_name": localized(80, r["ckl"][0])
                if r["aeV"] == 3 and r["ckl"]
                else {},
            }
            for r in row["cjK"]
        ]
        result.append(
            {
                "id": quest_id,
                "title": localized(62, quest_id),
                "description": localized(63, quest_id),
                "category": localized(61, row["cjG"]),
                "native": row,
                "objectives": objectives,
                "rewards": rewards,
                "dialogue_references": by_quest.get(quest_id, []),
            }
        )
    return {
        "note": "Literal references are conditions, not proven dialogue transitions or NPC bindings.",
        "definitions": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quest", type=int, help="Filter to one native definition ID")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with (ROOT / ".runtime/quest-extraction/native-quest-definitions.json").open() as f:
        definitions = json.load(f)
    with (ROOT / ".runtime/quest-reconstruction/dialogue-references.json").open() as f:
        refs = json.load(f)
    result = build(definitions, refs)
    if args.quest is not None:
        result["definitions"] = [
            x for x in result["definitions"] if x["id"] == args.quest
        ]
        if not result["definitions"]:
            parser.error("unknown definition ID")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(result['definitions'])} definitions: {args.output}")


if __name__ == "__main__":
    main()
