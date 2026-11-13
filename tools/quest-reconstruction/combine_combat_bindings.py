#!/usr/bin/env python3
"""Combine reconstructed monster and dungeon bindings, rejecting duplicates."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / ".runtime/quest-reconstruction"


def combine(documents):
    if not documents:
        raise ValueError("Missing input documents")
    schema, revision = documents[0]["schema"], documents[0]["revision"]
    rows = []
    for document in documents:
        if document["schema"] != schema or document["revision"] != revision:
            raise ValueError("Different native revisions")
        rows.extend(document["bindings"])
    for key in ("quest_id", "objective_id"):
        if len({row[key] for row in rows}) != len(rows):
            raise ValueError("Duplicate combat mission " + key)
    return {
        "schema": schema,
        "revision": revision,
        "bindings": sorted(rows, key=lambda row: row["quest_id"]),
    }


def main():
    docs = [
        json.loads((PATH / name).read_text())
        for name in ("named-combat-bindings.json", "dungeon-combat-bindings.json")
    ]
    result = combine(docs)
    (PATH / "combat-mission-batch.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"{len(result['bindings'])} unique bindings")


if __name__ == "__main__":
    main()
