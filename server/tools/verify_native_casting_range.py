"""Bulk-check the shared range formula against original offline Java bytecode."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.combat_casting_range import effective_range


def cases_from_catalog(path):
    with open(path, "rt") as stream:
        spells = json.load(stream)["spells"]
    contracts = set()
    rows = 0
    for spell in spells.values():
        for minimum, maximum, *_ in spell["levels"]:
            contracts.add((minimum, maximum, spell["range_modifiable"]))
            rows += 1
        for branch in spell.get("conditional", []):
            for minimum, maximum in branch["ranges"]:
                contracts.add((minimum, maximum, branch["range_modifiable"]))
                rows += 1
    # Additional boundary cases ensure zero/negative maxima and cap below minimum.
    contracts.update(
        itertools.product((-2, 0, 1, 2, 5), (-3, 0, 1, 2, 6), (False, True))
    )
    scenarios = sorted(
        (*contract, bonus, carried, cap)
        for contract in contracts
        for bonus, carried, cap in itertools.product(
            (-(1 << 31), -20, -3, -1, 0, 1, 3, 20, (1 << 31) - 1),
            (False, True),
            (False, True),
        )
    )
    return spells, rows, contracts, scenarios


def reference_formula(minimum, maximum, modifiable, bonus, carried, cap):
    return effective_range(minimum, maximum, modifiable, bonus, carried, cap)[1]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--java", default="java")
    parser.add_argument("--classpath", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spells, rows, contracts, scenarios = cases_from_catalog(args.catalog)
    payload = "".join(
        ",".join(str(value).lower() for value in case) + "\n" for case in scenarios
    )
    native = subprocess.run(
        [args.java, "-cp", args.classpath, "ProbeNativeCastingRange"],
        input=payload,
        text=True,
        capture_output=True,
        check=True,
    )
    actual = [int(line) for line in native.stdout.splitlines()]
    if len(actual) != len(scenarios):
        raise ValueError("Incomplete native oracle output")
    mismatches = [
        dict(case=case, native=value, python=reference_formula(*case))
        for case, value in zip(scenarios, actual)
        if value != reference_formula(*case)
    ]
    report = dict(
        source_sha256=hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        spell_count=len(spells),
        table_level_rows=rows,
        distinct_contracts=len(contracts),
        scenarios=len(scenarios),
        mismatches=mismatches,
        native_metadata=native.stderr.strip(),
        scope="Final fcj range formula only; conditional selection and eHl snapshot are separate contracts",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
