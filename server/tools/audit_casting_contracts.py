"""Offline, catalog-wide casting contract inventory; never executes a fight."""
import argparse
import hashlib
import json
from pathlib import Path


CAST_FLAGS = ("line_of_sight", "linear", "free_cell", "range_modifiable")


def audit_contracts(native_spells, class_spells, inventory_rows):
    """Group missing metadata and table differences without spell whitelists."""
    ownership = {str(row["id"]): row for row in inventory_rows}
    groups = {}

    def record(group, reference):
        groups.setdefault(group, set()).add(str(reference))

    for reference, definition in native_spells.items():
        levels = definition.get("levels", [])
        for field in CAST_FLAGS:
            if type(definition.get(field)) is not bool:
                record("baseline_missing_" + field, reference)
        if not levels:
            record("baseline_missing_levels", reference)
        if any(row[1] == 0 for row in levels):
            record("baseline_zero_maximum", reference)
        for conditional in definition.get("conditional", []):
            if not conditional.get("criteria"):
                record("conditional_missing_criteria", reference)
            for field in CAST_FLAGS:
                if type(conditional.get(field)) is not bool:
                    record("conditional_missing_" + field, reference)
            ranges = conditional.get("ranges", [])
            if len(ranges) != len(levels):
                record("conditional_range_level_count_mismatch", reference)
            if any(
                tuple(alternate) != tuple(base[:2])
                for alternate, base in zip(ranges, levels)
            ):
                record("conditional_range_varies", reference)
            for field in CAST_FLAGS:
                if (
                    field in definition
                    and field in conditional
                    and definition[field] != conditional[field]
                ):
                    record("conditional_" + field + "_varies", reference)
        baseline = class_spells.get(reference)
        if baseline is not None:
            baseline_levels = baseline.get("levels", [])
            if len(baseline_levels) != len(levels):
                record("class_baseline_level_count_differs", reference)
            if any(
                class_level != native_level
                for class_level, native_level in zip(baseline_levels, levels)
            ):
                record("class_baseline_levels_or_roots_mismatch", reference)
            for field in CAST_FLAGS:
                if (
                    field in baseline
                    and field in definition
                    and baseline[field] != definition[field]
                ):
                    record("class_baseline_" + field + "_mismatch", reference)
    for reference in class_spells:
        if reference not in native_spells:
            record("class_missing_native_casting_definition", reference)

    result = {}
    for group, references in sorted(groups.items()):
        active = [
            ownership[r]
            for r in references
            if r in ownership and ownership[r].get("kind") == "active"
        ]
        class_rows = [ownership[r] for r in references if r in ownership]
        result[group] = {
            "native_spell_count": len(references),
            "class_spell_count": len(class_rows),
            "active_class_spell_count": len(active),
            "class_ids": sorted({row["breed"] for row in class_rows}),
            "active_class_ids": sorted({row["breed"] for row in active}),
            "spell_ids": sorted(map(int, references)),
            "active_class_spell_ids": sorted(row["id"] for row in active),
        }
    return {
        "scope": "Offline static contracts; groups are overlapping, not gameplay pass/fail counts.",
        "native_spell_count": len(native_spells),
        "class_baseline_count": len(class_spells),
        "class_inventory_count": len(ownership),
        "native_conditional_spell_count": sum(
            bool(row.get("conditional")) for row in native_spells.values()
        ),
        "groups": result,
    }


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=root
        / "docs/reports/combat-inventory/casting-contract-review-20261007.json",
    )
    args = parser.parse_args()
    sources = {
        "native": root / "server/protocol/native-spell-casting.json",
        "class": root / "server/protocol/spell-effect-trees.json",
        "inventory": root / "docs/reports/combat-inventory/inventory.json",
    }
    with open(sources["native"], "rt") as stream:
        native = json.load(stream)["spells"]
    classes = json.loads(sources["class"].read_text())["spells"]
    inventory = json.loads(sources["inventory"].read_text())["spells"]
    report = audit_contracts(native, classes, inventory)
    report["sources_sha256"] = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sources.values()
    }
    report["source_code_sha256"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Casting contract inventory — 2026-10-07",
        "",
        report["scope"],
        "",
        f"Reviewed {report['native_spell_count']} native definitions, {report['class_baseline_count']} class baselines and {report['class_inventory_count']} class inventory records.",
        "",
        "| Shared contract group | Native definitions | Class spells | Active class spells | Classes |",
        "|---|---:|---:|---:|---|",
    ]
    for name, group in report["groups"].items():
        lines.append(
            f"| {name} | {group['native_spell_count']} | {group['class_spell_count']} | {group['active_class_spell_count']} | {', '.join(map(str, group['class_ids']))} |"
        )
    lines += [
        "",
        "Missing range-modifiable metadata blocks a faithful general range resolver. Conditional variation identifies where baseline-only validation can disagree with the selected native table; it does not assert that every branch is reachable in every deck.",
        "",
        "Use one complete casting-table selector for ordinary and granted spells, followed by the native live-actor range calculation. Keep zero-range and unmodifiable spells explicit. Implement and verify shared contracts before investigating individual spell behavior.",
        "",
        "All impacted spell IDs and source SHA256 hashes are in the adjacent JSON. Regenerate with `python3 server/tools/audit_casting_contracts.py`. No runtime state is accessed.",
        "",
    ]
    args.output.with_suffix(".md").write_text("\n".join(lines))
    print(
        json.dumps(
            {
                "output": str(args.output),
                "native_spell_count": report["native_spell_count"],
                "groups": len(report["groups"]),
            }
        )
    )


if __name__ == "__main__":
    main()
