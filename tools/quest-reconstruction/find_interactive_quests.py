#!/usr/bin/env python3
"""Find native interactive/quest predicate references; never infer activation or edges."""
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREDICATE = re.compile(
    r"IsAchievement(Active|Running|Complete|ObjectiveComplete)\s*\(\s*(\d+)\s*\)"
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--definitions",
        type=Path,
        default=ROOT / ".runtime/quest-extraction/native-quest-definitions.json",
    )
    parser.add_argument(
        "--objects",
        type=Path,
        default=ROOT / "agents_docs/reports/ENVIRONMENT-OBJECTS-20261011.csv",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.definitions.read_text())
    definitions = {r["d"]: r for r in data["definitions"]}
    objectives = {o["d"]: row["d"] for row in data["definitions"] for o in row["cjJ"]}
    text = data["translations"]["es"]
    actions = json.loads(
        (
            ROOT / "server/wakfu_server/items/native_achievement_item_actions.json"
        ).read_text()
    )["actions"]
    starters = {a["definition_id"]: a for a in actions}
    rows = []
    for obj in csv.DictReader(args.objects.open()):
        try:
            native = json.loads(obj["native_outcome_definitions"])
        except (ValueError, TypeError):
            continue
        if not isinstance(native, dict):
            continue
        for state in native.get("states", []):
            for outcome in state.get("outcomes", []):
                expressions = [("outcome", outcome.get("criteria", ""))]
                expressions.extend(
                    ("effect", x.get("criteria", ""))
                    for x in outcome.get("effects", [])
                )
                for source, expr in expressions:
                    if not isinstance(expr, str):
                        continue
                    for match in PREDICATE.finditer(expr):
                        kind, raw_id = match.groups()
                        value = int(raw_id)
                        quest = (
                            objectives.get(value)
                            if kind == "ObjectiveComplete"
                            else value
                        )
                        definition = definitions.get(quest)
                        exact_positive_active = (
                            kind in ("Active", "Running")
                            and re.fullmatch(
                                r"\s*IsAchievement(?:Active|Running)\s*\(\s*\d+\s*\)\s*",
                                expr,
                            )
                            is not None
                        )
                        if not definition:
                            continue
                        target = definition["cjJ"]
                        single = len(target) == 1
                        rows.append(
                            {
                                "quest_id": quest,
                                "objective_id": target[0]["d"] if single else None,
                                "referenced_objective_id": value
                                if kind == "ObjectiveComplete"
                                else None,
                                "quest_name_es": text.get(f"content.62.{quest}"),
                                "objective_text_es": text.get(
                                    f"content.64.{target[0]['d']}"
                                )
                                if single
                                else None,
                                "objective_count": len(target),
                                "quest_criterion": definition["cjI"],
                                "map_id": int(obj["map_id"]),
                                "object_id": int(obj["object_id"]),
                                "x": int(float(obj["x"])),
                                "y": int(float(obj["y"])),
                                "z": int(float(obj["z"])),
                                "object_type": obj["type"],
                                "template_id": native.get("id"),
                                "native_action_id": state.get("action"),
                                "native_state_id": state.get("id"),
                                "wire_action_id": 0
                                if quest == 1197 and obj["object_id"] == "18153"
                                else None,
                                "wire_parameter": 0
                                if quest == 1197 and obj["object_id"] == "18153"
                                else None,
                                "required_item": state.get("cod"),
                                "required_quantity": state.get("coe"),
                                "consume_flag_native": state.get("cof"),
                                "outcome": outcome,
                                "predicate_source": source,
                                "predicate": match.group(),
                                "criterion": expr,
                                "activation": starters.get(quest),
                                "status": (
                                    "tested_hot_reference"
                                    if quest == 1197 and obj["object_id"] == "18153"
                                    else "candidate_single_objective"
                                    if single and exact_positive_active
                                    else "reference_only"
                                ),
                                "evidence": "Client predicate is conditional evidence, not proof of objective completion or wire mapping.",
                            }
                        )
    counts = Counter(x["status"] for x in rows)
    result = {
        "source": {"definitions": str(args.definitions), "objects": str(args.objects)},
        "counts": dict(counts),
        "unique_quests": len({x["quest_id"] for x in rows}),
        "unique_objects": len({(x["map_id"], x["object_id"]) for x in rows}),
        "references": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "references"}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
