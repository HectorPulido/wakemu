#!/usr/bin/env python3
"""Index localized item-handoff clues and literal dialogue conditions.

This is an evidence index, not an executable mission policy. Text matches and
item thresholds do not establish consumption, dialogue destinations, or NPCs.
"""

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OBJECTIVE = re.compile(
    r"\b(?:entregar(?:le|les)?|entrega|darle|darles|llevarle|llevarles|llevar|traerle|traerles|ofrecer(?:le|les)?|d[aá]rsel[oa]s?)\b",
    re.I,
)
QUEST = re.compile(
    r"\b(?:IsAchievementRunning|IsAchievementActive|IsAchievementComplete|CanResetAchievement)\s*\(\s*(\d+)\s*\)"
)
OBJECTIVE_REF = re.compile(r"\bIsAchievementObjectiveComplete\s*\(\s*(\d+)\s*\)")
ITEM = re.compile(r"\bGetItemQuantity\s*\(\s*(\d+)\s*\)\s*(>=|<=|==|!=|>|<)\s*(\d+)")


def index(definitions, dialogues):
    translations = definitions["translations"]
    spanish = translations["es"]
    owners = {o["d"]: d["d"] for d in definitions["definitions"] for o in d["cjJ"]}
    by_quest = defaultdict(list)
    for node in dialogues["nodes"]:
        for option in node["choices"]:
            expression = option.get("criteria", "") or ""
            node_expression = node.get("criteria", "") or ""
            items = [
                {"item_id": int(item), "operator": op, "quantity": int(qty)}
                for item, op, qty in ITEM.findall(expression + " " + node_expression)
            ]
            if not items:
                continue
            combined = expression + " " + node_expression
            ids = {int(q) for q in QUEST.findall(combined)}
            ids.update(
                owners[int(o)]
                for o in OBJECTIVE_REF.findall(combined)
                if int(o) in owners
            )
            for identity in ids:
                by_quest[identity].append(
                    {
                        "node_id": node["id"],
                        "choice_id": option["id"],
                        "node_criterion": node_expression,
                        "choice_criterion": expression,
                        "item_thresholds": items,
                        "node_text_es": dialogues["translations"]["es"].get(
                            f"content.75.{node['id']}"
                        ),
                        "choice_text_es": dialogues["translations"]["es"].get(
                            f"content.76.{option['id']}"
                        ),
                    }
                )
    candidates = []
    for d in definitions["definitions"]:
        if d["aeV"] not in (1, 2, 3, 4, 5):
            continue
        objectives = []
        for obj in d["cjJ"]:
            key = f"content.64.{obj['d']}"
            text = spanish.get(key, "")
            if OBJECTIVE.search(text):
                objectives.append(
                    {
                        "id": obj["d"],
                        "text": {
                            lang: words.get(key) for lang, words in translations.items()
                        },
                        "native": obj,
                    }
                )
        if objectives:
            candidates.append(
                {
                    "id": d["d"],
                    "category_type": d["aeV"],
                    "title": {
                        lang: words.get(f"content.62.{d['d']}")
                        for lang, words in translations.items()
                    },
                    "level": d["cjP"],
                    "period_seconds": d["cjU"],
                    "duration_seconds": d["cjL"],
                    "availability": d["cjI"],
                    "objectives": objectives,
                    "dialogue_item_evidence": by_quest.get(d["d"], []),
                }
            )
    return candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    quest_path = ROOT / ".runtime/quest-extraction/native-quest-definitions.json"
    dialogue_path = ROOT / "database/protocol/npc-dialogues.json.gz"
    definitions = json.loads(quest_path.read_bytes())
    with gzip.open(dialogue_path, "rt") as source:
        dialogues = json.load(source)
    rows = index(definitions, dialogues)
    counts = {
        "definitions": len(rows),
        "objectives": sum(len(r["objectives"]) for r in rows),
        "periodic_definitions": sum(r["period_seconds"] > 0 for r in rows),
        "with_dialogue_item_criteria": sum(
            bool(r["dialogue_item_evidence"]) for r in rows
        ),
        "category_types": dict(
            sorted(Counter(str(r["category_type"]) for r in rows).items())
        ),
    }
    output = {
        "schema": "item-turnin-objective-clues-v1",
        "counts": counts,
        "note": "Text is a search clue. Item tests are literal conditions only; no consumption, transition or recipient inferred.",
        "sources_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (quest_path, dialogue_path)
        },
        "candidates": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
