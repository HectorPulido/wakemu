"""Join offline range flags by exact native reference and conditional criteria."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path


def merge_flags(casting, flags):
    """Reject incomplete or ambiguous exports; never invent missing flags."""
    base = casting["spells"]
    imported = flags["spells"]
    if set(base) != set(imported):
        raise ValueError(
            "Native spell references differ between casting and flag exports"
        )
    result = deepcopy(casting)
    conditional_spell_count = 0
    for reference, definition in result["spells"].items():
        row = imported[reference]
        if type(row.get("range_modifiable")) is not bool:
            raise ValueError(f"Missing native baseline range flag: {reference}")
        definition["range_modifiable"] = row["range_modifiable"]
        exported = row.get("conditional", [])
        by_criteria = {}
        for conditional in exported:
            criteria = conditional.get("criteria")
            if not isinstance(criteria, str) or criteria in by_criteria:
                raise ValueError(f"Ambiguous native flag criteria: {reference}")
            if type(conditional.get("range_modifiable")) is not bool:
                raise ValueError(f"Missing native conditional flag: {reference}")
            by_criteria[criteria] = conditional["range_modifiable"]
        native_conditions = definition.get("conditional", [])
        criteria = [condition["criteria"] for condition in native_conditions]
        if len(set(criteria)) != len(criteria) or set(criteria) != set(by_criteria):
            raise ValueError(f"Native conditional criteria differ: {reference}")
        for conditional in native_conditions:
            conditional["range_modifiable"] = by_criteria[conditional["criteria"]]
        conditional_spell_count += bool(native_conditions)
    result["range_flag_import"] = {
        "source": flags.get("source"),
        "spell_count": len(base),
        "conditional_spell_count": conditional_spell_count,
        "join": "Exact reference and conditional criteria; missing/duplicate data rejected",
    }
    return result


def read_json(path):
    opener = open
    with opener(path, "rt") as stream:
        return json.load(stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--casting", type=Path, required=True)
    parser.add_argument("--flags", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    staging = (root / ".runtime").resolve()
    if not output.is_relative_to(staging):
        raise ValueError(
            "Output must stay under .runtime staging; protocol files are never overwritten"
        )
    if output in {args.casting.resolve(), args.flags.resolve()}:
        raise ValueError("Output must differ from both input catalogs")
    merged = merge_flags(read_json(args.casting), read_json(args.flags))
    merged["range_flag_import"]["sources_sha256"] = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (args.casting, args.flags)
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        stream.write((json.dumps(merged, separators=(",", ":")) + "\n").encode())
    print(json.dumps(merged["range_flag_import"]))


if __name__ == "__main__":
    main()
