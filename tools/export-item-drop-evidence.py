#!/usr/bin/env python3
"""Export reproducible native combat drop evidence; SELECT-only PostgreSQL access."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess

SUPPORTED = {
    "NOT_IN_DUNGEON",
    "ONLY_IN_DUNGEON",
    "NOT_IN_INFINITE_WAVES",
    "ONLY_WHEN_DOWNSCALED",
    "CAN_BE_LOOTED_IN_STELE",
    "MIN_STASIS_LEVEL",
    "MIN_SCORE",
}


def query(sql):
    return subprocess.check_output(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "wakemu",
            "-d",
            "wakemu_runtime",
            "-At",
            "-c",
            sql,
        ],
        text=True,
    ).rstrip("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--revision",
        default="677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runtime/local/item-pricing-20261011/drops.json"),
    )
    args = parser.parse_args()
    if len(args.revision) != 64 or any(
        c not in "0123456789abcdef" for c in args.revision
    ):
        raise ValueError("Expected immutable SHA256 revision")
    sources = {}
    documents = {}
    for name in ("monster-encyclopedia.json", "monsters.json"):
        raw = bytes.fromhex(
            query(
                f"SELECT encode(raw,'hex') FROM native_catalog_documents WHERE revision='{args.revision}' AND path='{name}'"
            )
        )
        recorded = query(
            f"SELECT sha256 FROM native_catalog_documents WHERE revision='{args.revision}' AND path='{name}'"
        )
        if hashlib.sha256(raw).hexdigest() != recorded:
            raise ValueError("Source document hash mismatch")
        documents[name] = json.loads(raw)
        sources[name] = recorded
    metadata = {m["ref"]: m for m in documents["monsters.json"]["monsters"]}
    items = {}
    for monster in documents["monster-encyclopedia.json"]["monsters"]:
        meta = metadata.get(monster["ref"], {})
        properties = monster["raw_native"].get("csc", [])
        boss = next(
            (
                label
                for code, label in (
                    (49, "ultimate_boss"),
                    (99, "raid_boss"),
                    (43, "boss"),
                    (45, "arch"),
                )
                if code in properties
            ),
            "regular",
        )
        for index, row in enumerate(monster["combat_drops"]):
            conditions = row.get("conditions", [])
            reasons = []
            if row.get("is_loot_table") is not False:
                reasons.append("external_loot_table")
            if row.get("complex_criteria") is not False:
                reasons.append("opaque_complex_criteria")
            if any(
                c.get("native_enum") not in SUPPORTED
                or (
                    c["native_enum"] not in ("MIN_SCORE", "MIN_STASIS_LEVEL")
                    and c.get("value") != -1
                )
                for c in conditions
            ):
                reasons.append("unsupported_condition")
            probability = Decimal(str(row["probability"]))
            if probability <= 0:
                reasons.append("zero_probability")
            attempts = max(1, row["roll_count"])
            route = dict(
                row,
                monster_reference=monster["ref"],
                row_index=index,
                monster_name=meta.get("name"),
                monster_min_level=meta.get("min_level"),
                monster_max_level=meta.get("max_level"),
                boss_classification=boss,
                runtime_supported=not reasons,
                exclusion_reasons=reasons,
                attempt_count=attempts,
                probability_at_least_one_base=float(
                    1 - (1 - min(Decimal(1), probability)) ** attempts
                ),
                expected_quantity_base=float(
                    probability
                    * attempts
                    * Decimal(row["quantity_min"] + row["quantity_max"])
                    / 2
                ),
            )
            items.setdefault(str(row["reference_id"]), {"routes": []})["routes"].append(
                route
            )
    states = Counter()
    for item in items.values():
        valid = [r for r in item["routes"] if r["runtime_supported"]]
        baseline = [r for r in valid if not r["conditions"] and r["native_csF"] <= 100]
        item["status"] = (
            "supported_unconditional"
            if baseline
            else "supported_conditional_or_pp"
            if valid
            else "matching_rows_unusable"
        )
        states[item["status"]] += 1
        item["matching_row_count"] = len(item["routes"])
        item["supported_route_count"] = len(valid)
        item["unconditional_route_count"] = len(baseline)

        def key(r):
            return (
                -r["probability_at_least_one_base"],
                r["monster_min_level"] if r["monster_min_level"] is not None else 99999,
                r["monster_reference"],
                r["row_index"],
            )

        item["best_supported_route"] = min(valid, key=key) if valid else None
        item["best_unconditional_route"] = min(baseline, key=key) if baseline else None
    output = dict(
        schema_version=1,
        revision=args.revision,
        source_sha256=sources,
        probability_units="fraction; 0.01 = 1 percent",
        missing_reference_status="no_matching_native_combat_drop_record; not proof of no acquisition route",
        selection="highest base probability of at least one success; then lowest monster minimum level",
        summary=dict(states),
        items=items,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    print(
        json.dumps(
            {"items": len(items), "states": dict(states), "output": str(args.output)}
        )
    )


if __name__ == "__main__":
    main()
