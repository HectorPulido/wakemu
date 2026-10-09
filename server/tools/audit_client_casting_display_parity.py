#!/usr/bin/env python3
"""Bulk native tooltip versus authoritative target range, without runtime catalogs.

Branch tables and synthetic input snapshots expose contract differences, not
reachability of a particular equipment/state/carry configuration.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.combat_casting_range import effective_range, int32

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    with open(path, "rt") as stream:
        return json.load(stream)


def run(output):
    paths = [
        ROOT / "server/protocol/native-spell-casting.json",
        ROOT / "server/protocol/native-class-spell-level-zero.json",
        ROOT
        / "docs/reports/combat-inventory/class-native-mechanic-components-20261007.json",
    ]
    before = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    }
    spells = read(paths[0])["spells"]
    zero = read(paths[1])["casting"]
    components = read(paths[2])["classes"]
    ownership = {}
    for component in components:
        for reference in component["class_spell_ids"] + component["class_extra_ids"]:
            ownership.setdefault(reference, []).append(component["breed"])
    scenarios = (
        (0, 0, False, False),
        (3, 0, False, False),
        (-3, 0, False, False),
        (0, 2, False, False),
        (3, -2, False, False),
        (0, 0, True, False),
        (0, 0, False, True),
    )
    counts, examples, by_class, conditional_refs = Counter(), {}, {}, set()
    tables = evaluations = 0
    missing = []
    for reference, breeds in sorted(ownership.items()):
        records = [
            (False, spells.get(str(reference))),
            (True, zero.get(str(reference))),
        ]
        for is_zero, record in records:
            if record is None:
                missing.append(dict(reference=reference, level_zero=is_zero))
                continue
            variants = [("baseline", record)] + [
                (branch["criteria"], branch) for branch in record["conditional"]
            ]
            if record["conditional"]:
                conditional_refs.add(reference)
            for branch, table in variants:
                ranges = table.get("ranges", table["levels"])
                for index, values in enumerate(ranges):
                    level = 0 if is_zero else index + 1
                    minimum, maximum = values[:2]
                    modifiable = table["range_modifiable"]
                    tables += 1
                    for bonus, category, carried, capped in scenarios:
                        effective_base = int32(maximum + category)
                        tooltip = max(
                            minimum,
                            int32(effective_base + (bonus if modifiable else 0)),
                        )
                        mask = effective_range(
                            minimum, effective_base, modifiable, bonus, carried, capped
                        )[1]
                        evaluations += 1
                        reason = (
                            "property2_cap"
                            if capped
                            else "carried_bonus"
                            if carried
                            else "maximum_below_one_gate"
                            if effective_base < 1
                            else "minimum_clamp"
                        )
                        key = "equal" if tooltip == mask else reason
                        counts[key] += 1
                        for breed in breeds:
                            by_class.setdefault(str(breed), Counter())[key] += 1
                        if tooltip != mask:
                            sample = dict(
                                reference=reference,
                                breeds=breeds,
                                level=level,
                                branch=branch,
                                minimum=minimum,
                                maximum=maximum,
                                modifiable=modifiable,
                                range_bonus=bonus,
                                category_bonus=category,
                                carried=carried,
                                property2=capped,
                                tooltip_maximum=tooltip,
                                target_mask_maximum=mask,
                            )
                            bucket = examples.setdefault(reason, [])
                            if len(bucket) < 18 and not any(
                                x["reference"] == reference for x in bucket
                            ):
                                bucket.append(sample)
    after = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    }
    result = dict(
        scope="All native class spell table levels including zero, baseline and conditional branches",
        class_count=len(components),
        owned_references=len(ownership),
        native_range_tables=tables,
        input_scenario_evaluations=evaluations,
        comparisons=dict(counts),
        by_class=by_class,
        examples=examples,
        missing_records=missing,
        conditional_references=sorted(conditional_refs),
        sources=before,
        sources_stable=before == after,
        native_proof="bPO.elJ tooltip and fcj.a target-mask bytecode; earlier 7200 range oracle and native tooltip probe",
        limitations=[
            "Input scenarios are contract probes; state/equipment reachability is not asserted.",
            "Tooltip selects with null target; actual casting uses actual target. Conditional predicate selection requires separate runtime evidence.",
            "No live UI render or reconnect result is implied. Costs, deck levels and packet delivery are separate authorities.",
        ],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                tables=tables,
                evaluations=evaluations,
                comparisons=counts,
                missing=len(missing),
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
