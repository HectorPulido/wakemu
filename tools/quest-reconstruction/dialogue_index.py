#!/usr/bin/env python3
"""Index literal achievement/objective references in native dialogue criteria."""

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PATTERN = re.compile(
    r"\b(IsAchievementRunning|IsAchievementComplete|IsAchievementActive|CanResetAchievement|IsAchievementObjectiveComplete)\s*\(\s*(\d+)\s*\)"
)


def build(catalog):
    rows = []
    for node in catalog["nodes"]:
        for choice in [None, *node["choices"]]:
            criterion = node["criteria"] if choice is None else choice["criteria"]
            for match in PATTERN.finditer(criterion):
                predicate, identifier = match.groups()
                rows.append(
                    {
                        "kind": (
                            "objective"
                            if predicate == "IsAchievementObjectiveComplete"
                            else "achievement"
                        ),
                        "id": int(identifier),
                        "predicate": predicate,
                        "node_id": node["id"],
                        "choice_id": None if choice is None else choice["id"],
                        "criteria": criterion,
                        "text": {
                            lang: {
                                "node": texts.get(f"content.75.{node['id']}"),
                                "speaker": texts.get(f"content.159.{node['id']}"),
                                "choice": (
                                    None
                                    if choice is None
                                    else texts.get(f"content.76.{choice['id']}")
                                ),
                            }
                            for lang, texts in catalog["translations"].items()
                        },
                    }
                )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", type=Path, default=ROOT / "database/protocol/npc-dialogues.json.gz"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with gzip.open(args.catalog, "rt", encoding="utf-8") as source:
        catalog = json.load(source)
    rows = build(catalog)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        json.dump(
            {
                "source": str(args.catalog),
                "note": "Literal criteria references only; no inferred graph edges or NPC bindings.",
                "references": rows,
            },
            output,
            ensure_ascii=False,
            indent=2,
        )
        output.write("\n")
    print(
        f'{len(rows)} references: {dict(Counter(row["kind"] for row in rows))}; {args.output}'
    )


if __name__ == "__main__":
    main()
