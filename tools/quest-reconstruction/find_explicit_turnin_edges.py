#!/usr/bin/env python3
"""Find explicit turn-in clues; output is evidence, not a gameplay publication.

A match requires one item threshold, a positive running predicate for the same
mission, and a negative completion predicate naming one of its delivery
objectives. Full predicates remain attached: this tool never resolves NPC
placements, interprets every condition, authorizes item consumption, or guesses
dialogue edges. Ambiguous OR/False expressions are intentionally excluded.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / ".runtime/quest-reconstruction/item-turnin-objective-clues.json"
DEFAULT_OUTPUT = ROOT / ".runtime/quest-reconstruction/explicit-turnin-edges.json"
OR_FALSE = re.compile(r"\bor\b|\|\||\bfalse\b", re.I)
NEG_OBJECTIVE = re.compile(
    r"(?:\bnot\s+|!\s*)IsAchievementObjectiveComplete\s*\(\s*(\d+)\s*\)", re.I
)
NEG_RUNNING = re.compile(
    r"(?:\bnot\s+|!\s*)IsAchievementRunning\s*\(\s*(\d+)\s*\)", re.I
)


def collect(document):
    results = []
    for quest in document["candidates"]:
        qid = quest["id"]
        objectives = {o["id"]: o for o in quest["objectives"]}
        for choice in quest["dialogue_item_evidence"]:
            expression = choice["choice_criterion"]
            if OR_FALSE.search(expression) or OR_FALSE.search(
                choice.get("node_criterion", "")
            ):
                continue
            items = choice["item_thresholds"]
            matched = NEG_OBJECTIVE.findall(expression)
            positive = re.search(
                r"\bIsAchievementRunning\s*\(\s*" + str(qid) + r"\s*\)",
                expression,
                re.I,
            )
            negatives = {int(i) for i in NEG_RUNNING.findall(expression)}
            if (
                len(items) != 1
                or items[0]["operator"] != ">="
                or len(matched) != 1
                or not positive
                or qid in negatives
            ):
                continue
            oid = int(matched[0])
            if oid not in objectives:
                continue
            results.append(
                {
                    "quest_id": qid,
                    "quest_title": quest["title"],
                    "category_type": quest["category_type"],
                    "level": quest["level"],
                    "period_seconds": quest["period_seconds"],
                    "duration_seconds": quest["duration_seconds"],
                    "quest_availability": quest["availability"],
                    "objective_id": oid,
                    "objective_text": objectives[oid]["text"],
                    "item_id": items[0]["item_id"],
                    "minimum_quantity": items[0]["quantity"],
                    "node_id": choice["node_id"],
                    "choice_id": choice["choice_id"],
                    "node_criterion": choice["node_criterion"],
                    "choice_criterion": expression,
                    "node_text_es": choice["node_text_es"],
                    "choice_text_es": choice["choice_text_es"],
                }
            )
    return sorted(
        results,
        key=lambda r: (r["quest_id"], r["objective_id"], r["node_id"], r["choice_id"]),
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()
    raw = args.input.read_bytes()
    rows = collect(json.loads(raw))
    out = {
        "schema": "explicit-turnin-clues-v1",
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "counts": {
            "choices": len(rows),
            "quests": len({x["quest_id"] for x in rows}),
            "nodes": len({x["node_id"] for x in rows}),
        },
        "note": "Evidence only: no claim about NPC binding, item consumption, transition, or availability.",
        "candidates": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(out["counts"]))


if __name__ == "__main__":
    main()
