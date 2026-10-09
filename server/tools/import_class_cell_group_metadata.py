"""Extract exact class eYk metadata from the full native graph, without catalogs."""
import argparse
import hashlib
import json
from pathlib import Path


def extract(source):
    effects = {}
    with open(source, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("kind") != "effect" or row.get("family") != 349:
                continue
            reference = str(row["reference"])
            if reference in effects:
                raise ValueError("Duplicate native class cell-group definition")
            effects[reference] = dict(
                criterion_present=row["criterion_native"] is not None,
                area_class=row["native_metadata"]["area_class"],
                raw_parameters=row["raw_parameters"],
            )
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(
        schema="native-eYk-class-cell-group-v1",
        source="original native class mechanic graph",
        source_sha256=digest,
        effects=effects,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(extract(args.source), sort_keys=True, indent=2) + "\n"
    )
