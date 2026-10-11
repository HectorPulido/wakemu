"""Plan bounded missing native spell exports from typed dependency closures.

Follows existing native304/321/307/315/649 authorities. A discovered spell is
source data, never an additional owned spell or an activation certificate.
"""
import argparse
import json
from pathlib import Path
import subprocess

from export_monster_summon_dependencies import compact, dependency_closure, read_bundle
from convert_spell_effect_trees import convert
from monster_spell_supplement import (
    source_inputs,
    sha256_file,
    validate_supplement_domains,
    merge_dependency_supplement,
    verify_spell_supplement,
)


def missing_spell_plan(tables, monsters, references, casting, *, limit=16):
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("Invalid bounded native spell supplement limit")
    closures, missing = {}, set()
    for reference in sorted(set(references)):
        if type(reference) is not int or str(reference) not in monsters:
            raise ValueError("Unknown native monster supplement reference")
        monster = monsters[str(reference)]
        closure = dependency_closure(
            tables,
            monsters,
            [ability["spell_id"] for ability in monster["native_abilities"]],
            monster["initial_state_triples"][::3],
        )
        closures[str(reference)] = closure
        missing.update(
            int(value.split(":", 1)[1])
            for value in closure["missing_definitions"]
            if value.startswith("spells:") and int(value.split(":", 1)[1]) > 0
        )
    present, absent = sorted(missing & set(map(int, casting))), sorted(
        missing - set(map(int, casting))
    )
    if len(present) > limit:
        raise ValueError("Missing native spell supplement exceeds bounded limit")
    return dict(
        schema="native-monster-missing-spell-supplement-v1",
        offline=True,
        closures=closures,
        export_spell_ids=present,
        absent_installed_casting_ids=absent,
        ownership_changed=False,
        activated=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--reference", type=int, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--spell-supplement", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    before = source_inputs(args.bundle)
    tables = {kind: {} for kind in ("spells", "states", "areas", "effects")}
    for name in ("trees", "states", "area-effects", "areas"):
        document = compact(read_bundle(args.bundle, name))
        for kind, rows in document.items():
            for key, row in rows.items():
                if key in tables[kind] and tables[kind][key] != row:
                    raise ValueError("Conflicting native closure component")
                tables[kind][key] = row
    if args.spell_supplement is not None:
        tables = merge_dependency_supplement(
            tables, verify_spell_supplement(args.spell_supplement, args.bundle)
        )
    monsters = {
        str(row["ref"]): row for row in read_bundle(args.bundle, "monsters")["monsters"]
    }
    casting = read_bundle(args.bundle, "casting")["spells"]
    plan = missing_spell_plan(tables, monsters, args.reference, casting)
    (args.output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    if args.extract and plan["export_spell_ids"]:
        references = args.output / "references.txt"
        references.write_text(
            "".join(f"{reference}\n" for reference in plan["export_spell_ids"])
        )
        prefix = args.output / "native"
        classes = args.output / "classes"
        classes.mkdir()
        exporter = (
            Path(__file__).resolve().parents[2]
            / "sniffer/java/ExportGrantedSpellEffectTrees.java"
        )
        subprocess.run(
            [
                "javac",
                "-proc:none",
                "-cp",
                "client/lib/*",
                "-d",
                str(classes),
                str(exporter),
            ],
            check=True,
        )
        subprocess.run(
            [
                "java",
                "-Xmx768m",
                "-cp",
                str(classes) + ":client/lib/*",
                "ExportGrantedSpellEffectTrees",
                str(references),
                str(prefix),
            ],
            check=True,
        )
        supplement = convert(prefix, args.output / "trees.json")
        if set(map(int, supplement["spells"])) != set(plan["export_spell_ids"]):
            raise ValueError("Native supplement export reference mismatch")
        supplement["casting"] = {
            str(reference): casting[str(reference)]
            for reference in plan["export_spell_ids"]
        }
        for reference, spell in supplement["spells"].items():
            source = casting[reference]
            if (
                len(spell["levels"]) != source["maximum_level"]
                or len(source["costs"]) != source["maximum_level"]
            ):
                raise ValueError("Incomplete native spell level or cost domain")
        (args.output / "supplement.json").write_text(
            json.dumps(supplement, separators=(",", ":")) + "\n"
        )
        domains = validate_supplement_domains(supplement)
        if source_inputs(args.bundle) != before:
            raise ValueError("Native supplement source changed during export")
        artifacts = (
            "plan.json",
            "references.txt",
            "native-effects.tsv",
            "native-spells.tsv",
            "trees.json",
            "supplement.json",
        )
        receipt = dict(
            schema="native-spell-supplement-receipt-v1",
            offline=True,
            source_sha256=before,
            output_sha256={name: sha256_file(args.output / name) for name in artifacts},
            domains=domains,
            ownership_changed=False,
            activated=False,
        )
        (args.output / "source-receipt.json").write_text(
            json.dumps(receipt, indent=2) + "\n"
        )
    print(
        json.dumps(
            {
                key: plan[key]
                for key in ("export_spell_ids", "absent_installed_casting_ids")
            }
        )
    )


if __name__ == "__main__":
    main()
