"""Preserve names, compile native weapon effects and list damage-only candidates."""
import json
from collections import Counter
from pathlib import Path
import os
import tempfile

from convert_spell_effect_trees import read_effects


def atomic_text(path, text):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix="weapon-export-")
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def convert(rules_path, effects_tsv, effects_output, names_path, audit_path):
    rules = json.loads(Path(rules_path).read_text())
    names = {
        row["reference"]: row["name"]
        for row in json.loads(Path(names_path).read_text())["items"]
    }
    effects = read_effects(effects_tsv)
    candidates, other = [], []
    for item in rules["items"]:
        item["name"] = names.get(item["reference"], "")
        families = sorted(
            {effects[str(root["reference"])]["effect_class"] for root in item["roots"]}
        )
        record = dict(
            reference=item["reference"],
            name=item["name"],
            families=families,
            ap_cost=item["ap_cost"],
        )
        # Structural candidates, not a claim that runtime behavior is verified.
        (
            candidates
            if families and set(families) <= {1, 2, 3, 4, 5, 917, 1083}
            else other
        ).append(record)
    atomic_text(rules_path, json.dumps(rules, ensure_ascii=False, indent=2) + "\n")
    descriptor, temporary = tempfile.mkstemp(
        dir=Path(effects_output).parent, prefix="weapon-export-"
    )
    os.close(descriptor)
    try:
        with open(temporary, "wt") as output:
            json.dump(
                dict(source="Installed native weapon effect trees", effects=effects),
                output,
                separators=(",", ":"),
            )
        os.replace(temporary, effects_output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    audit = dict(
        status="Structural inventory; execution and GUI checks pending",
        templates=len(rules["items"]),
        effects=len(effects),
        damage_only_candidates=candidates,
        other_templates=other,
    )
    candidate_ids = {item["reference"] for item in candidates}
    audit["damage_areas"] = dict(
        Counter(
            effects[str(root["reference"])]["area_native"]
            for item in rules["items"]
            if item["reference"] in candidate_ids
            for root in item["roots"]
        )
    )
    audit["missing_names"] = sum(not item["name"] for item in rules["items"])
    audit[
        "cost_mapping"
    ] = "Native fcH: gjf=AP, gji=MP, gjh=WP; fnR.cmZ supplies effect level."
    atomic_text(audit_path, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(candidates)} damage-only candidates, {len(other)} other templates")


if __name__ == "__main__":
    import sys

    convert(*sys.argv[1:])
