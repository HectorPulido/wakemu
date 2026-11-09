#!/usr/bin/env python3
"""Compare HostLab scenario or private-request outcomes offline."""
import argparse
import json
import sys


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def read_results(path):
    rows = {}
    mode = None
    with open(path, encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            row = json.loads(line, object_pairs_hook=unique_object)
            if not isinstance(row, dict):
                raise ValueError(f"Invalid HostLab result on line {number}")
            if isinstance(row.get("scenario"), str) and row["scenario"]:
                current_mode, name = "scenarios", row["scenario"]
                if type(row.get("passed")) is not bool or "action" not in row:
                    raise ValueError(f"Invalid scenario result on line {number}")
                passed, outcome = row["passed"], row["action"]
            elif type(row.get("sample")) is int and row["sample"] > 0:
                current_mode, name = "request", f"sample:{row['sample']}"
                if type(row.get("status")) is not int or not isinstance(
                    row.get("response"), dict
                ):
                    raise ValueError(f"Invalid request result on line {number}")
                if row["status"] == 200 and not isinstance(
                    row["response"].get("action"), dict
                ):
                    raise ValueError(f"Missing request action on line {number}")
                passed = row["status"] == 200
                outcome = {
                    "status": row["status"],
                    "action": row["response"].get("action"),
                }
            else:
                raise ValueError(f"Invalid HostLab result on line {number}")
            if mode is not None and mode != current_mode:
                raise ValueError("Cannot mix scenario and request results")
            mode = current_mode
            if name in rows:
                raise ValueError(f"Duplicate HostLab result on line {number}")
            rows[name] = (
                passed,
                json.dumps(
                    outcome, sort_keys=True, separators=(",", ":"), allow_nan=False
                ),
            )
    if not rows:
        raise ValueError("No HostLab results")
    return mode, rows


def compare(baseline, current):
    return [
        {
            "scenario": name,
            "change": (
                "missing_current"
                if name not in current
                else "new_scenario"
                if name not in baseline
                else "outcome_changed"
            ),
        }
        for name in sorted(baseline.keys() | current.keys())
        if name not in baseline
        or name not in current
        or baseline[name] != current[name]
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", help="HostLab JSON-lines results")
    parser.add_argument("current", help="HostLab JSON-lines results")
    args = parser.parse_args(argv)
    try:
        baseline_mode, baseline = read_results(args.baseline)
        current_mode, current = read_results(args.current)
        if baseline_mode != current_mode:
            raise ValueError("Cannot compare scenario and request results")
        changes = compare(baseline, current)
    except (OSError, ValueError, TypeError) as error:
        print(f"Cannot compare results ({type(error).__name__}).", file=sys.stderr)
        return 2
    failures = sorted(name for name, (passed, _) in current.items() if not passed)
    print(
        json.dumps(
            {
                "mode": current_mode,
                "baselineScenarios": len(baseline),
                "currentScenarios": len(current),
                "changes": changes,
                "currentFailures": failures,
            },
            separators=(",", ":"),
        )
    )
    return 1 if changes or failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
