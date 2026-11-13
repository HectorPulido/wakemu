#!/usr/bin/env python3
"""Index client mission combat text as evidence, never as event bindings."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DUNGEON = re.compile(
    r"\b(vencer|vence|venc[eé]is|venc[ée]|terminar|termina|termin[eé]is)\b.*\bmazmorra\b",
    re.I,
)
GOLEM = re.compile(r"\bg[oó]lem", re.I)


def extract(document):
    es = document["translations"]["es"]
    rows = []
    for definition in document["definitions"]:
        if definition["aeV"] not in (1, 2, 3, 4, 5):
            continue
        for objective in definition["cjJ"]:
            text = es.get(f"content.64.{objective['d']}", "")
            labels = [
                label
                for label, pattern in (
                    ("dungeon_combat_text", DUNGEON),
                    ("golem_text", GOLEM),
                )
                if pattern.search(text)
            ]
            if not labels:
                continue
            rows.append(
                {
                    "definition_id": definition["d"],
                    "objective_id": objective["d"],
                    "title_es": es.get(f"content.62.{definition['d']}"),
                    "objective_es": text,
                    "description_es": es.get(f"content.63.{definition['d']}"),
                    "labels": labels,
                    "native_type": definition["aeV"],
                    "level": definition["cjP"],
                    "duration_seconds": definition["cjL"],
                    "period_seconds": definition["cjU"],
                    "native_anchor_ms": definition["cjT"],
                    "visibility_criterion": definition["aHe"],
                    "activation_criterion": definition["cjI"],
                    "objective_criteria": [objective["ckc"], objective["cke"]],
                    "markers": objective["ckd"],
                    "native_rewards": definition["cjK"],
                    "all_objective_ids": [row["d"] for row in definition["cjJ"]],
                    "event_binding": None,
                }
            )
    counts = Counter(label for row in rows for label in row["labels"])
    return {
        "schema_version": 1,
        "source_sha256": document.get("source_sha256", {}),
        "warning": "Text matches are candidates, not verified target, initiation, timing, victory, or reward semantics.",
        "counts": dict(counts),
        "definitions": len({row["definition_id"] for row in rows}),
        "candidates": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / ".runtime/quest-extraction/native-quest-definitions.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime/quest-reconstruction/combat-quest-candidates.json",
    )
    args = parser.parse_args()
    data = extract(json.loads(args.input.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"{data['definitions']} definitions; {data['counts']}; {args.output}")


if __name__ == "__main__":
    main()
