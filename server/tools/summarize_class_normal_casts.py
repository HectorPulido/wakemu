"""Summarize completed offline cast evidence without importing combat catalogs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def summarize(report):
    groups = {}
    contexts = Counter()
    for case in report["rows"]:
        runtime = case.get("runtime_access", {})
        records = [(None, runtime)]
        for action in runtime.get("actions", []):
            selection = action.get("target_selection", {})
            if not selection.get("eligible") and selection.get("status"):
                contexts[(action["origin"], selection["status"])] += 1
            records.extend(
                (action, record) for record in (action.get("attempts") or [action])
            )
        for action, record in records:
            failure = record.get("first_root_failure")
            if not failure:
                continue
            family = (failure.get("first_failed_effect") or {}).get("effect_class")
            reason = failure.get("root_reason", failure.get("reason"))
            kind = failure["kind"]
            # Original eXR.fPC invokes GS.ne(0) when all conditional children
            # are excluded. This requires a real prerequisite context, not a
            # weakened lottery guard or an invented successful no-op.
            if (
                family == 341
                and reason
                == "Native GS.ne requires positive remaining probability total"
            ):
                kind = "native_random_pool_context_invalid"
            key = (kind, family, reason)
            group = groups.setdefault(
                key,
                dict(
                    kind=key[0],
                    effect_class=family,
                    reason=reason,
                    occurrences=0,
                    classes=set(),
                    spell_level_pairs=set(),
                    origins=set(),
                    failed_stages=Counter(),
                ),
            )
            group["occurrences"] += 1
            group["classes"].add(case["breed"])
            group["failed_stages"][record.get("failed_stage", "runtime_access")] += 1
            if action:
                group["spell_level_pairs"].add(
                    (case["breed"], case["level"], action["reference"])
                )
                group["origins"].add(action["origin"])
    result = []
    for group in groups.values():
        group["classes"] = sorted(group["classes"])
        group["spell_level_pairs"] = sorted(group["spell_level_pairs"])
        group["distinct_spell_level_pairs"] = len(group["spell_level_pairs"])
        group["origins"] = sorted(group["origins"])
        group["failed_stages"] = dict(group["failed_stages"])
        group["requires_implementation_review"] = group["kind"] not in (
            "legal_target_rejection",
            "resource_rejection",
            "legal_baseline_context_unavailable",
            "native_random_pool_context_invalid",
        )
        result.append(group)
    result.sort(
        key=lambda row: (
            not row["requires_implementation_review"],
            -len(row["classes"]),
            -row["distinct_spell_level_pairs"],
            -row["occurrences"],
        )
    )
    return dict(
        numeric_summary=report["numeric_summary"],
        inventory_complete=report["all_requested_class_decks_reached"],
        source_tool_stable=report["normal_tool_stable"],
        priorities=result,
        target_context_counts=[
            dict(origin=origin, status=status, count=count)
            for (origin, status), count in sorted(contexts.items())
        ],
        limitation="Bounded target searches and baseline contexts do not establish global spell eligibility; repeated grants are not additional normal spell coverage.",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = args.input.read_bytes()
    output = summarize(json.loads(source))
    output["source_report_sha256"] = hashlib.sha256(source).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            dict(
                inventory_complete=output["inventory_complete"],
                priority_groups=len(output["priorities"]),
                numeric_summary=output["numeric_summary"],
            )
        )
    )
