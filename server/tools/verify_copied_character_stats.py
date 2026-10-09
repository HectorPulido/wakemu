"""Compare original eHI constructor rows with the scoped Python producer."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.combat_character_copy_stats import copy_characteristics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text())
    oracle = json.loads(args.oracle.read_text())
    definitions = metadata["fresh_characteristics"]
    maxima = {
        int(k): max(v["hard_minimum"], min(v["hard_maximum"], v["maximum"]))
        for k, v in definitions.items()
    }
    currents = {
        int(k): max(v["hard_minimum"], min(maxima[int(k)], v["current"]))
        for k, v in definitions.items()
    }
    for stat, maximum, current in ((1, 250, 125), (2, 9, 3), (3, 6, 2), (4, 6, 4)):
        maxima[stat], currents[stat] = maximum, current
    mismatches = []
    checked = 0
    for row in oracle:
        copied = copy_characteristics(
            currents,
            maxima,
            fresh_definitions=definitions,
            breed_curves={},
            level=200,
            percentage=row["percentage"],
            maximum_caps={},
            native_order=tuple(metadata["native_characteristic_order"]),
        )
        actual = {
            c.identifier: [c.identifier, c.current, c.minimum, c.maximum, c.percentage]
            for c in copied
        }
        expected = {c[0]: c for c in row["characteristics"]}
        checked += len(expected)
        for identity in sorted(set(actual) | set(expected)):
            if actual.get(identity) != expected.get(identity):
                mismatches.append(
                    dict(
                        percentage=row["percentage"],
                        characteristic=identity,
                        actual=actual.get(identity),
                        expected=expected.get(identity),
                    )
                )
    output = dict(
        scope="Original eHI scalar constructor with default eGW/no eGK registrations; six ratios",
        checked_characteristics=checked,
        mismatches=mismatches,
        inputs={
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (args.metadata, args.oracle, Path(__file__))
        },
    )
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(dict(checked=checked, mismatches=len(mismatches))))
    return bool(mismatches)


if __name__ == "__main__":
    raise SystemExit(main())
