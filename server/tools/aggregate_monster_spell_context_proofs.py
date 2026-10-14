"""Aggregate exact executed contexts; projections never become monster qualification."""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def aggregate(index):
    cache = collections.defaultdict(list)
    for case in index["actual_case_cache"]:
        cache[
            (
                case["reference"],
                case["actor_level"],
                case["spell_id"],
                case["spell_level"],
            )
        ].append(case)
    expected = collections.defaultdict(set)
    for key, spell in index["spell_index"].items():
        for context in spell["resolved_native_level_contexts"]:
            parameter = context["native_level_parameter"]
            for low, high in context["native_actor_ranges"]:
                for level in range(low, high + 1):
                    spell_level = level if parameter == -1 else parameter
                    expected[context["ref"]].add(
                        (context["ref"], level, int(key), spell_level)
                    )
    rows = []
    for ref, contexts in sorted(expected.items()):
        observed = contexts & cache.keys()
        validated = {
            key
            for key in observed
            if any(c["status"] == "validated" for c in cache[key])
        }
        rows.append(
            {
                "reference": ref,
                "expected_exact_native_contexts": len(contexts),
                "observed_exact_native_contexts": len(observed),
                "validated_exact_native_contexts": len(validated),
                "missing_exact_native_contexts": len(contexts - observed),
                "pending_exact_native_contexts": len(observed - validated),
                "native_initialization_receipt_count": sum(
                    len(c.get("native_initialization_receipts", []))
                    for key in observed
                    for c in cache[key]
                ),
                "constructor_and_ai_qualification_transferred": False,
                "proof_keys": sorted(
                    {c["proof_key"] for key in observed for c in cache[key]}
                ),
                "status": "exact_case_coverage_complete_requires_constructor_ai_and_source_review"
                if contexts == validated
                else "exact_native_context_coverage_incomplete",
                "monster_qualified": False,
                "source_compatibility_assumed": False,
            }
        )
    projections = [
        {
            "block_id": block["block_id"],
            "spell_ids": block["spell_ids"],
            "refs": block["refs"],
            "status": "source_dependency_requires_implementation_or_integration",
            "actual_execution_transferred": False,
        }
        for block in index["blocks"]
        if block["kind"] == "verified_runtime_gap"
    ]
    return {
        "schema": "monster-exact-spell-context-aggregation-v1",
        "rows": rows,
        "receipt_contexts": index["receipt_contexts"],
        "source_projections": projections,
        "live_policy_mutated": False,
        "admission": False,
        "source_compatibility_not_inferred_from_equal_spell_ids": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output must be new")
    result = aggregate(json.loads(args.index.read_text()))
    result["index_sha256"] = hashlib.sha256(args.index.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(
        json.dumps(
            {
                "refs": len(result["rows"]),
                "observed_contexts": sum(
                    row["observed_exact_native_contexts"] for row in result["rows"]
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
