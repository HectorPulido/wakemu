#!/usr/bin/env python3
"""Index native recurring-dialogue item turn-in candidates, without activating them."""
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
RESET = re.compile(r"\bCanResetAchievement\((\d+)\)")
RUNNING = re.compile(r"\bIsAchievementRunning\((\d+)\)")
ITEM = re.compile(r"\bGetItemQuantity\((\d+)\)\s*>=\s*(\d+)")
FALSE = re.compile(r"\bFalse\b", re.I)


def collect(dialogues, definitions):
    offers, turnins = defaultdict(list), defaultdict(list)
    translations = dialogues["translations"]
    for node in dialogues["nodes"]:
        for option in node["choices"]:
            expression = option["criteria"]
            row = {
                "node_id": node["id"],
                "choice_id": option["id"],
                "criteria": expression,
                "text": {
                    lang: words.get(f"content.76.{option['id']}")
                    for lang, words in translations.items()
                },
            }
            for identity in RESET.findall(expression):
                offers[int(identity)].append(row)
            items = [
                {"item_id": int(i), "quantity": int(q)}
                for i, q in ITEM.findall(expression)
            ]
            if items:
                for identity in RUNNING.findall(expression):
                    turnins[int(identity)].append({**row, "item_thresholds": items})
    native = {d["d"]: d for d in definitions["definitions"]}
    text = definitions["translations"]
    result = []
    for identity in sorted(offers.keys() & turnins.keys() & native.keys()):
        row = native[identity]
        result.append(
            {
                "id": identity,
                "title": {
                    lang: words.get(f"content.62.{identity}")
                    for lang, words in text.items()
                },
                "period_seconds": row["cjU"],
                "anchor_ms": row["cjT"],
                "native": row,
                "offers": offers[identity],
                "turnins": turnins[identity],
                "contains_false_condition": any(
                    FALSE.search(x["criteria"])
                    for x in offers[identity] + turnins[identity]
                ),
                "note": "Literal references only: quantity thresholds are not proof of consumption, dialogue edges, NPC placement or completion.",
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with gzip.open(ROOT / "server/protocol/npc-dialogues.json.gz", "rt") as f:
        dialogues = json.load(f)
    with (ROOT / ".runtime/quest-extraction/native-quest-definitions.json").open() as f:
        definitions = json.load(f)
    candidates = collect(dialogues, definitions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {"schema_version": 1, "candidates": candidates},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(
        f"{len(candidates)} definitions, {sum(not c['contains_false_condition'] for c in candidates)} without literal False: {args.output}"
    )


if __name__ == "__main__":
    main()
