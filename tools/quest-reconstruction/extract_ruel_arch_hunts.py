#!/usr/bin/env python3
"""Export Ruel's native offer predicates and arch-hunt definitions as evidence.

This tool does not authorize NPC placements, choose missions or mutate progress.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUESTS = ROOT / ".runtime/quest-extraction/native-quest-definitions.json"
DEFAULT_DIALOGUES = ROOT / "server/protocol/npc-dialogues.json.gz"


def build(quest_file, dialogue_file):
    raw_quests, raw_dialogues = quest_file.read_bytes(), dialogue_file.read_bytes()
    quests = json.loads(raw_quests)
    dialogue = json.loads(gzip.decompress(raw_dialogues))
    translations = quests["translations"]
    texts = dialogue["translations"]

    def localized(prefix, identity, source):
        key = f"content.{prefix}.{identity}"
        return {
            language: values[key]
            for language, values in source.items()
            if key in values
        }

    hunts = []
    for row in quests["definitions"]:
        if row["cjG"] != 681:
            continue
        hunts.append(
            {
                "id": row["d"],
                "title": localized(62, row["d"], translations),
                "description": localized(63, row["d"], translations),
                "objectives": [
                    {"native": obj, "text": localized(64, obj["d"], translations)}
                    for obj in row["cjJ"]
                ],
                "native": row,
            }
        )
    nodes = []
    for row in dialogue["nodes"]:
        if row["id"] not in (4099, 4142, 4144, 4146, 4150, 4194, 4195):
            continue
        nodes.append(
            {
                "native": row,
                "text": localized(75, row["id"], texts),
                "choices": [
                    {"native": c, "text": localized(76, c["id"], texts)}
                    for c in row["choices"]
                ],
            }
        )
    return {
        "schema": "ruel-arch-hunt-evidence-v1",
        "note": "Native fields and predicates only. Node transitions, actor placement, and selection policy are not established.",
        "category_id": 681,
        "preceding_quest_id": 3974,
        "definitions": sorted(hunts, key=lambda x: x["id"]),
        "dialogue_nodes": nodes,
        "source_sha256": {
            "quest_export": hashlib.sha256(raw_quests).hexdigest(),
            "dialogue_catalog": hashlib.sha256(raw_dialogues).hexdigest(),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quests", type=Path, default=DEFAULT_QUESTS)
    parser.add_argument("--dialogues", type=Path, default=DEFAULT_DIALOGUES)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime/quest-reconstruction/ruel-arch-hunts.json",
    )
    args = parser.parse_args()
    doc = build(args.quests, args.dialogues)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print(
        f"{len(doc['definitions'])} definitions; {len(doc['dialogue_nodes'])} dialogue nodes: {args.output}"
    )


if __name__ == "__main__":
    main()
