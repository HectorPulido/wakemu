"""Qualify native quest-marker candidates without treating markers as actor spawns."""
import argparse
import json
from collections import Counter
from pathlib import Path


def qualify(rows):
    records = []
    for row in rows:
        reasons = []
        if (
            not row.get("unique_speaker_name")
            or len(row.get("candidate_references", [])) != 1
        ):
            reasons.append("ambiguous_speaker")
        if row.get("geometry_status") != "exact_walkable":
            reasons.append("unverified_walkable_cell")
        roots = row.get("candidate_unconditional_portrait_roots", [])
        if len(roots) != 1:
            reasons.append("missing_or_ambiguous_initial_root")
        # The installed objective schema supplies compass coordinates, not actor identity.
        # Native spawn/root evidence must be added explicitly by a future extractor.
        if row.get("position_contract") != "native_actor_spawn":
            reasons.append("quest_marker_is_not_actor_spawn")
        if row.get("speaker_contract") != "native_actor_breed_reference":
            reasons.append("localized_name_is_not_native_breed_join")
        if row.get("root_contract") != "native_initial_dialogue_binding":
            reasons.append("portrait_is_not_initial_dialogue_binding")
        if row.get("visibility_contract") != "unconditional_native_world_actor":
            reasons.append("quest_visibility_not_accredited")
        records.append(
            {**row, "activation_qualified": not reasons, "rejection_reasons": reasons}
        )
    return {
        "schema": "native-npc-placement-qualification-v1",
        "counts": {
            "candidates": len(records),
            "activation_qualified": sum(r["activation_qualified"] for r in records),
            "rejections": dict(
                Counter(reason for r in records for reason in r["rejection_reasons"])
            ),
        },
        "records": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = qualify(json.loads(args.source.read_text()))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["counts"]))
