"""Bulk literal state/deck dependencies of all class and granted cast tables."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from import_class_summon_dependencies import entries

ROOT = Path(__file__).resolve().parents[2]


def state_references(record):
    criteria = [
        record.get("cast_criterion_raw"),
        *(row.get("criteria") for row in record.get("conditional", ())),
    ]
    return {
        int(value)
        for criterion in criteria
        if isinstance(criterion, str)
        for value in re.findall(
            r"(?:HasState|GetStateLevel|GetStateDuration)\(\s*(\d+)", criterion
        )
    }


def export(access_inventory):
    casting = ROOT / "server/protocol/native-spell-casting.json"
    inventory = json.loads(access_inventory.read_text())
    wanted = {str(row["id"]) for row in inventory["class_spells"]}
    wanted.update(map(str, inventory["granted_spell_references"]))
    records = {}
    for reference, row in entries(casting, "spells"):
        if reference not in wanted:
            continue
        criteria = [
            dict(
                location="cast",
                raw=row.get("cast_criterion_raw"),
                native_present=row["cast_criterion_native_present"],
            )
        ]
        criteria += [
            dict(location=f"conditional:{index}", raw=value["criteria"])
            for index, value in enumerate(row["conditional"])
        ]
        records[reference] = dict(
            criteria=criteria, literal_state_dependencies=sorted(state_references(row))
        )
    with casting.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(
        schema="native-class-spell-state-access-v1",
        casting_sha256=digest,
        inventory_sha256=hashlib.sha256(access_inventory.read_bytes()).hexdigest(),
        counts=dict(
            references=len(records),
            state_dependent=sum(
                bool(row["literal_state_dependencies"]) for row in records.values()
            ),
        ),
        spells=records,
        missing_references=sorted(wanted - set(records)),
        limitations=[
            "Literal dependencies select audit cases only; actual native criteria authorize every cast.",
            "Dynamic state expressions are retained raw and not guessed.",
            "Conditional range/cost criteria are distinct from mandatory cast criteria.",
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = export(args.inventory)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["counts"], sort_keys=True))
