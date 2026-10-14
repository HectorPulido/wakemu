"""Include native minimum-zero books in offline scope at positive actor levels.

This changes inventory and work selection only, never native data or activation.
Existing encounter/class exclusions remain admission obligations.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def positive_actor_interval(monster):
    low, high = monster["min_level"], monster["max_level"]
    if low < 0 or high < max(1, low):
        return None
    return [max(1, low), high]


def expand(base, native, eligible_refs):
    eligible = set(eligible_refs)
    additions = []
    for monster in native:
        if (
            monster["ref"] in eligible
            or monster["min_level"] != 0
            or not monster["abilities"]
        ):
            continue
        interval = positive_actor_interval(monster)
        if interval is None:
            continue
        additions.append(
            {
                "reference": monster["ref"],
                "name": monster["name"],
                "category": "new_positive_level_scope_pending_producer_and_execution",
                "native_range": [monster["min_level"], monster["max_level"]],
                "validation_ranges": [interval],
                "owned_spell_ids": sorted(
                    {a["spell_id"] for a in monster["abilities"]}
                ),
                "initial_state_ids": sorted(
                    {s["state_id"] for s in monster["initial_states"]}
                ),
                "ordinary_wild_admission": "requires_existing_class_and_encounter_policy",
                "native_source_changed": False,
                "admission": False,
            }
        )
    added = {row["reference"] for row in additions}
    total = len(eligible | added)
    result = dict(base)
    result.update(
        schema="positive-level-monster-scope-v1",
        eligible_scope=total,
        unpublished=base["unpublished"] + len(added),
        published_percent_of_eligible=round(100 * base["published_enabled"] / total, 4),
        unpublished_percent_of_eligible=round(
            100 * (base["unpublished"] + len(added)) / total, 4
        ),
        outside_eligible_count=base["outside_eligible_count"] - len(added),
        eligible_references=sorted(eligible | added),
        added_minimum_zero_references=sorted(added),
        minimum_validation_actor_level=1,
        rows=base["rows"] + additions,
        live_policies_not_mutated=True,
    )
    result["unpublished_exclusive_categories"] = dict(
        base["unpublished_exclusive_categories"]
    )
    result["unpublished_exclusive_categories"][
        "new_positive_level_scope_pending_producer_and_execution"
    ] = len(added)
    result["outside_eligible_exclusive_categories"] = dict(
        base["outside_eligible_exclusive_categories"]
    )
    result["outside_eligible_exclusive_categories"][
        "owned_but_native_minimum_zero"
    ] -= len(added)
    assert (
        sum(result["unpublished_exclusive_categories"].values())
        == result["unpublished"]
    )
    assert (
        sum(result["outside_eligible_exclusive_categories"].values())
        == result["outside_eligible_count"]
    )
    return result, additions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--eligible", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    args = parser.parse_args()
    base = json.loads(args.base.read_text())
    with gzip.open(args.native, "rt") as stream:
        native = json.load(stream)["monsters"]
    eligible = {m["ref"] for m in json.loads(args.eligible.read_text())["monsters"]}
    result, additions = expand(base, native, eligible)
    result["scope_input_sha256"] = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (args.base, args.native, args.eligible)
    }
    jobs = [
        {
            "ref": row["reference"],
            "name": row["name"],
            "uncovered_ranges": row["validation_ranges"],
            "group": "positive_level_scope_pending_producer_policy",
        }
        for row in additions
    ]
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    args.queue.write_text(
        json.dumps(
            {
                "schema": "positive-level-scope-work-v1",
                "jobs": jobs,
                "admission": False,
                "minimum_actor_level": 1,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "eligible_scope",
                    "published_enabled",
                    "unpublished",
                    "published_percent_of_eligible",
                    "outside_eligible_count",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
