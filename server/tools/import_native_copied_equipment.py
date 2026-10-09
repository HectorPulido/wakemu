"""Import a completed native PJ definition snapshot without changing services."""
import argparse
import hashlib
import json
from pathlib import Path

from wakfu_server.combat_copied_equipment_plan import SOURCE, copied_equipment_plan


def build_catalog(path):
    definitions = {}
    completed = None
    with path.open() as stream:
        for line in stream:
            row = json.loads(line)
            if completed is not None:
                raise ValueError("Data after native equipment completion marker")
            if row.get("export_completed") is True:
                completed = row
                continue
            reference = row.get("reference")
            if type(reference) is not int or str(reference) in definitions:
                raise ValueError("Missing unique native equipment identity")
            definitions[str(reference)] = row
    if completed is None or completed.get("definition_count") != len(definitions):
        raise ValueError("Incomplete native equipment export")
    result = dict(
        schema=1,
        producer=SOURCE,
        complete=True,
        definition_count=len(definitions),
        definitions=definitions,
        source_jsonl_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    for reference in definitions:
        copied_equipment_plan(int(reference), result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build_catalog(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(result, separators=(",", ":"), allow_nan=False).encode()
    args.output.write_bytes(data)
    print(
        json.dumps(
            dict(
                definitions=result["definition_count"],
                sha256=hashlib.sha256(data).hexdigest(),
            )
        )
    )


if __name__ == "__main__":
    main()
