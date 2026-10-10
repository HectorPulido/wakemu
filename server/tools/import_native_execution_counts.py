"""Merge complete native listener count coefficients into retained metadata."""

import argparse
import hashlib
import json
from pathlib import Path


def merge_counts(metadata, exported):
    if (
        exported.get("schema") != "native-execution-counts-v1"
        or exported.get("complete") is not True
        or exported.get("count") != len(exported.get("effects", {}))
        or not exported.get("effects")
    ):
        raise ValueError("Incomplete native execution-count export")
    effects = {}
    for reference, row in metadata["effects"].items():
        native = exported["effects"].get(reference)
        if native is None or native["effect_class"] != row["effect_class"]:
            raise ValueError(f"Native count definition identity mismatch: {reference}")
        if native["event_execution_count"] != row["event_execution_count"]:
            raise ValueError(f"Native count base mismatch: {reference}")
        slope = native["event_execution_count_per_level"]
        if isinstance(slope, bool) or not isinstance(slope, (int, float)):
            raise ValueError(f"Missing native count coefficient: {reference}")
        effects[reference] = dict(row, event_execution_count_per_level=slope)
    return dict(metadata, effects=effects, execution_count_source=exported["source"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("exported", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    merged = merge_counts(
        json.loads(args.metadata.read_bytes()), json.loads(args.exported.read_bytes())
    )
    raw = json.dumps(
        merged, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    args.output.write_bytes(raw)
    print(
        json.dumps(
            {
                "effects": len(merged["effects"]),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
