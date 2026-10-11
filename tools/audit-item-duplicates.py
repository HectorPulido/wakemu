#!/usr/bin/env python3
"""Compare same-name retained items against frozen native catalog evidence."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def clean(value):
    """Remove only top-level item identity; retain nested association references."""
    if not isinstance(value, dict):
        return value
    return {
        k: v
        for k, v in value.items()
        if k not in {"reference", "name", "item_ref", "source_item_ref"}
    }


def semantic_record(record):
    result = json.loads(canonical(record))
    for section in ("item-equipment-effects.json", "item-healing-rules.json"):
        payload = result.get(section)
        if isinstance(payload, dict):
            for effect in payload.get("effects", []):
                effect.pop("id", None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path(".runtime/local/item-shop-inventory-20261011"),
    )
    parser.add_argument(
        "--curated",
        type=Path,
        default=Path("docs/reports/item-shop-inventory-20261011/curated"),
    )
    args = parser.parse_args()
    docs = json.loads((args.snapshot / "catalog.json").read_text())["documents"]
    indexes = {}
    for name, doc in docs.items():
        records = doc.get("items", doc.get("templates", doc.get("models", [])))
        if isinstance(records, dict):
            indexes[name] = {int(k): v for k, v in records.items()}
        else:
            grouped = defaultdict(list)
            for value in records:
                ref = value.get("reference", value.get("item_ref"))
                if ref is not None:
                    grouped[int(ref)].append(value)
            indexes[name] = {
                ref: values[0]
                if len(values) == 1
                else {"associations": [clean(v) for v in values]}
                for ref, values in grouped.items()
            }
    native = {
        v["reference"]: v
        for v in json.loads((args.snapshot / "native-types.json").read_text())["items"]
    }
    rows = list(csv.DictReader((args.curated / "all-items.csv").open()))
    groups = defaultdict(list)
    for row in rows:
        groups[row["name_es"]].append(row)
    groups = {name: rows for name, rows in groups.items() if len(rows) > 1}
    results, details = [], []
    difference_counts = defaultdict(int)
    for name, members in sorted(groups.items()):
        signatures = []
        for row in members:
            ref = int(row["reference"])
            record = {"native": clean(native.get(ref, {}))}
            record.update(
                {key: clean(index.get(ref)) for key, index in indexes.items()}
            )
            signatures.append(record)
        differences = [
            key
            for key in signatures[0]
            if len({canonical(s[key]) for s in signatures}) > 1
        ]
        semantic = [semantic_record(s) for s in signatures]
        semantic_differences = [
            key
            for key in signatures[0]
            if len({canonical(s[key]) for s in semantic}) > 1
        ]
        for key in differences:
            difference_counts[key] += 1
        classification = (
            "exported-record-equivalent"
            if not differences
            else (
                "effect-identity-only"
                if not semantic_differences
                else "structural-variants"
            )
        )
        result = {
            "name_es": name,
            "count": len(members),
            "references": "|".join(r["reference"] for r in members),
            "classification": classification,
            "different_sections": "|".join(differences),
            "semantic_different_sections": "|".join(semantic_differences),
            "levels": "|".join(sorted({r["level"] for r in members}, key=int)),
            "rarities": "|".join(
                sorted({r["native_rarity_id"] for r in members}, key=int)
            ),
            "types": "|".join(sorted({r["native_type_id"] for r in members}, key=int)),
        }
        results.append(result)
        for row, sig in zip(members, signatures):
            details.append(
                {
                    "name_es": name,
                    "reference": row["reference"],
                    "classification": classification,
                    "level": row["level"],
                    "rarity": row["native_rarity_id"],
                    "native_type_id": row["native_type_id"],
                    "gfx_id": row["gfx_id"],
                    "different_values_json": canonical(
                        {k: sig[k] for k in differences}
                    ),
                    "equipment_effect_record_present": indexes[
                        "item-equipment-effects.json"
                    ].get(int(row["reference"]))
                    is not None,
                }
            )
    for filename, data in [
        ("duplicates-groups.csv", results),
        ("duplicates-items.csv", details),
    ]:
        with (args.curated / filename).open("w") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    classes = {
        kind: sum(r["classification"] == kind for r in results)
        for kind in sorted({r["classification"] for r in results})
    }
    summary = {
        "retained_items": len(rows),
        "same_name_groups": len(results),
        "items_in_groups": len(details),
        "classifications_groups": classes,
        "different_sections_groups": dict(sorted(difference_counts.items())),
        "source_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                args.snapshot / "catalog.json",
                args.snapshot / "native-types.json",
                args.curated / "all-items.csv",
            )
        },
        "compared_sections": list(indexes),
    }
    (args.curated / "duplicates-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
