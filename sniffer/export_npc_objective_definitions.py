"""Export native defined objective identities for fail-closed NPC criteria."""
import argparse
import gzip
import json
from pathlib import Path


def export(source, destination):
    native = json.loads(source.read_text())
    objectives = {}
    for quest in native["definitions"]:
        for objective in quest["cjJ"]:
            objectives.setdefault(objective["d"], []).append(quest["d"])
    payload = json.dumps(
        dict(
            schema_version=1,
            source_sha256=native["source_sha256"],
            objectives=objectives,
        ),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    with destination.open("wb") as output:
        with gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as compressed:
            compressed.write(payload)
    return len(objectives)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(export(args.source, args.destination))
