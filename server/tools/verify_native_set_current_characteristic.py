#!/usr/bin/env python3
"""Compare the eWX kernel to original Java C/g/h for every fixed prototype."""
import argparse, hashlib, json, random, subprocess
from pathlib import Path
from wakfu_server.combat_set_current_characteristic import (
    set_current_registry,
    set_current_transition,
    remove_set_current_transition,
)

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rng = random.Random(560561562563)
    cases = []
    for family in map(int, set_current_registry()):
        for n in range(100):
            minimum, maximum = (-(2**31), 2**31 - 1) if n < 20 else (-5000, 50000)
            before = rng.randint(minimum, maximum)
            requested = rng.choice(
                [
                    minimum,
                    maximum,
                    0,
                    -1,
                    2**31 - 1,
                    -(2**31),
                    rng.randint(minimum, maximum),
                ]
            )
            row = dict(
                family=family,
                minimum=minimum,
                maximum=maximum,
                before=before,
                caster=requested,
                frozen=n % 7 == 0,
                intervening=rng.randint(minimum, maximum),
            )
            if n % 2:
                row["parameter"] = requested
            cases.append(row)
    command = [
        "/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java",
        "-Xmx128m",
        "-classpath",
        ".runtime/local/range-oracle-classes:client/lib/*",
        "ProbeNativeSetCurrentCharacteristic",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        input="".join(json.dumps(c) + "\n" for c in cases),
        capture_output=True,
        text=True,
        check=True,
    )
    rows = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]
    if len(rows) != len(cases):
        raise AssertionError("Native row count mismatch")
    mismatches = []
    for case, actual in zip(cases, rows):
        # Original fff effective getter observes the hard/effective clamp even
        # when expandable HP stores an additional raw current internally.
        before = max(case["minimum"], min(case["maximum"], case["before"]))
        requested = case.get("parameter", case["caster"])
        after, delta = set_current_transition(
            current=before,
            requested=requested,
            minimum=case["minimum"],
            maximum=case["maximum"],
            frozen=case["frozen"],
        )
        removal_before = max(case["minimum"], min(case["maximum"], case["intervening"]))
        removed = remove_set_current_transition(
            current=removal_before,
            delta=delta,
            minimum=case["minimum"],
            maximum=case["maximum"],
        )
        expected = dict(
            family=case["family"],
            calculated=requested,
            after=after,
            value=after,
            delta=delta,
            removal_before=removal_before,
            removed=removed,
        )
        if expected != actual:
            mismatches.append(dict(case=case, expected=expected, actual=actual))
    paths = [
        "sniffer/java/ProbeNativeSetCurrentCharacteristic.java",
        "server/wakfu_server/combat/combat_set_current_characteristic.py",
        "server/protocol/native-set-current-characteristic.json",
        "client/lib/wakfu-client.jar",
    ]
    report = dict(
        scope="Original isolated eWX C/g/h and real fff getters/setters, not complete gameplay",
        cases=len(cases),
        families=sorted(map(int, set_current_registry())),
        mismatches=mismatches,
        raw_expandable_storage_proven=False,
        sources_sha256={
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths
        },
    )
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(cases=len(cases), mismatches=len(mismatches))))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
