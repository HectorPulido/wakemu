"""Find affected native references from supplied dependency graphs, offline."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def affected_references(inventory, references, effect_ids):
    """Positive graph evidence only: missing edges never prove no impact."""
    if any(type(value) is not int or value <= 0 for value in effect_ids):
        raise ValueError("Invalid changed native effect identity")
    if any(type(value) is not int or value <= 0 for value in references):
        raise ValueError("Invalid native impact scope")
    selected = set(references)
    if len(selected) != len(references):
        raise ValueError("Duplicate native impact scope")
    effects, seen, rows = set(effect_ids), set(), []
    for monster in inventory:
        reference = monster["ref"]
        if type(reference) is not int or reference <= 0:
            raise ValueError("Invalid native inventory reference")
        if reference not in selected:
            continue
        if reference in seen:
            raise ValueError("Duplicate native impact reference")
        seen.add(reference)
        dependencies = monster["dependencies"]
        native_ids = dependencies["effect_ids"]
        if not isinstance(native_ids, list) or any(
            type(v) is not int or v <= 0 for v in native_ids
        ):
            raise ValueError("Missing native dependency effect identities")
        matching = sorted(effects.intersection(native_ids))
        if matching:
            rows.append(
                dict(
                    ref=reference,
                    name=monster["name"],
                    effect_ids=matching,
                    missing_definitions=dependencies.get("missing_definitions", []),
                    status="structural_dependency_replay_pending",
                )
            )
    if seen != selected:
        raise ValueError("Native impact scope missing from supplied inventory")
    return sorted(rows, key=lambda row: row["ref"])


def load(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as stream:
        return json.load(stream)


def digest(path):
    result = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument(
        "--effects",
        type=Path,
        required=True,
        help="Native metadata object keyed by exact effect reference",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    definitions = load(args.effects)
    if not isinstance(definitions, dict) or any(
        not key.isdecimal() for key in definitions
    ):
        raise ValueError("Expected native metadata keyed by effect identity")
    rows = affected_references(
        load(args.inventory)["monsters"],
        [r["ref"] for r in load(args.scope)["monsters"]],
        [int(key) for key in definitions],
    )
    result = dict(
        schema="native-monster-recovery-impacts-v1",
        offline=True,
        activated=False,
        runtime_validated=False,
        negative_evidence_complete=False,
        affected_count=len(rows),
        rows=rows,
        source_sha256={
            str(p): digest(p) for p in (args.inventory, args.scope, args.effects)
        },
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Found {len(rows)} affected references; no readiness or activation change")


if __name__ == "__main__":
    main()
