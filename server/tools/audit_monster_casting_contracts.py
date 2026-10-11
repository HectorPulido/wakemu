"""Report native self-centered ally-selector conflicts without changing runtime."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path


def level_contract(casting, effects, level):
    """Classify only the proven fcj range-zero / fcE bit128 contradiction."""
    levels = casting.get("levels")
    if not isinstance(levels, list) or not 1 <= level <= len(levels):
        return "unknown", "missing_positive_level_table"
    row = levels[level - 1]
    if not isinstance(row, list) or len(row) != 3:
        return "unknown", "malformed_level_table"
    minimum, maximum, roots = row
    if (minimum, maximum) != (0, 0):
        return "outside_pattern", "baseline_range_is_not_zero"
    if not isinstance(roots, list) or not roots:
        return "unknown", "missing_ordered_roots"
    unknown = False
    for root in roots:
        effect = effects.get(str(root))
        if not isinstance(effect, dict) or "native_target_selector" not in effect:
            unknown = True
            continue
        selector = effect["native_target_selector"]
        if selector is None:
            return "outside_pattern", "native_null_selector_accepts_target"
        if not isinstance(selector, dict) or selector.get("class") != "fcE":
            unknown = True
            continue
        mask = selector.get("mask")
        if type(mask) is not int or mask < 0:
            unknown = True
            continue
        if not mask & 128:
            return "outside_pattern", "root_does_not_require_other_ally"
    if unknown:
        return "unknown", "missing_exact_native_selector"
    if not isinstance(casting.get("conditional"), list):
        return "unknown", "missing_conditional_tables"
    if casting["conditional"]:
        return (
            "conditional_unknown",
            "baseline_conflicts_but_conditional_selection_unproven",
        )
    return (
        "blocked_native_ordinary_fcj",
        "zero_range_targets_caster_but_all_roots_require_other_ally",
    )


def audit(inventory, casting, effects):
    rows = []
    for monster in inventory["monsters"]:
        for ability in monster["abilities"]:
            reference = ability["spell_id"]
            table = casting.get(str(reference))
            if (
                not isinstance(table, dict)
                or type(table.get("maximum_level")) is not int
            ):
                rows.append(
                    dict(
                        ref=monster["ref"],
                        spell_id=reference,
                        status="unknown",
                        reason="missing_native_casting_definition",
                    )
                )
                continue
            override = ability["level_parameter"]
            requested = (
                (monster["min_level"], monster["max_level"])
                if override == -1
                else (override, override)
            )
            low, high = (min(value, table["maximum_level"]) for value in requested)
            findings = []
            for level in range(low, high + 1):
                status, reason = level_contract(table, effects, level)
                if status != "outside_pattern":
                    roots = (
                        table.get("levels", [])[level - 1][2]
                        if 1 <= level <= len(table.get("levels", []))
                        else []
                    )
                    findings.append(
                        dict(
                            spell_level=level,
                            status=status,
                            reason=reason,
                            root_ids=roots,
                        )
                    )
            if findings:
                statuses = {finding["status"] for finding in findings}
                if (
                    statuses == {"blocked_native_ordinary_fcj"}
                    and len(findings) == high - low + 1
                ):
                    status = "blocked_native_ordinary_fcj"
                elif "conditional_unknown" in statuses:
                    status = "conditional_unknown"
                elif "unknown" in statuses:
                    status = "unknown"
                else:
                    status = "partially_blocked_native_ordinary_fcj"
                rows.append(
                    dict(
                        ref=monster["ref"],
                        name=monster["name"],
                        min_level=monster["min_level"],
                        max_level=monster["max_level"],
                        spell_id=reference,
                        requested_level_range=list(requested),
                        normalized_level_range=[low, high],
                        status=status,
                        levels=findings,
                    )
                )
    return dict(
        schema="native-monster-casting-contract-audit-v1",
        runtime_changed=False,
        limitation="Only ordinary native fcj is proven. An alternate original NPC producer is not established; findings never enable monsters.",
        summary=dict(
            spell_rows=len(rows),
            reference_count=len({row["ref"] for row in rows}),
            status_counts=dict(Counter(row["status"] for row in rows)),
        ),
        monsters=rows,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    documents = {}
    hashes = {}
    for name in ("inventory", "casting", "trees"):
        path = args.bundle / (name + ".json.gz")
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with gzip.open(path, "rt") as stream:
            documents[name] = json.load(stream)
    report = audit(
        documents["inventory"],
        documents["casting"]["spells"],
        documents["trees"]["effects"],
    )
    report["source_document_sha256"] = hashes
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
