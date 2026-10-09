"""Inspect combat imports and prepare an offline export plan; never publish catalogs."""
import argparse
import hashlib
import json
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "native-spell-casting.json": ("spells",),
    "spell-effect-trees.json": ("spells", "effects"),
    "combat-state-definitions.json": ("states", "effects"),
    "granted-spell-effect-trees.json": ("spells", "effects"),
    "native-area-effect-trees.json": ("effects",),
    "native-npc-spell-effect-trees.json": ("spells", "effects"),
    "native-effect-areas.json": ("areas",),
    "breed-innate-definitions.json": ("breeds",),
}
EXPORTERS = [
    "ExportSpellEffectTrees",
    "ExportGrantedSpellEffectTrees",
    "ExportCombatStates",
    "ExportEffectAreaTrees",
    "ExportNativeEffectAreas",
]


def inspect():
    records, tables = {}, {}
    for name, keys in SOURCES.items():
        path = ROOT / "server/protocol" / name
        raw = path.read_bytes()
        data = json.loads(raw)
        for key in keys:
            if not isinstance(data.get(key), (dict, list)):
                raise ValueError(f"Invalid catalog collection {name}:{key}")
        tables[name] = data
        records[name] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "counts": {key: len(data[key]) for key in keys},
        }
    refs = sorted(map(int, tables["native-spell-casting.json"]["spells"]))
    covered = set()
    for name in (
        "spell-effect-trees.json",
        "granted-spell-effect-trees.json",
        "native-npc-spell-effect-trees.json",
    ):
        covered.update(tables[name]["spells"])
    missing = sorted(set(refs) - set(map(int, covered)))
    unresolved = {}
    for name, table in tables.items():
        effects = table.get("effects")
        if effects is not None:
            absent = {
                int(child)
                for effect in effects.values()
                for child in effect.get("children", [])
                if str(child) not in effects
            }
            unresolved[name] = sorted(absent)
    return {
        "catalogs": records,
        "casting_references": len(refs),
        "covered_spell_ids": len(covered),
        "missing_spell_tree_ids": missing,
        "unresolved_local_children": unresolved,
    }, refs


def plan(output):
    classes = output / "classes"
    classpath = str(classes) + ":" + str(ROOT / "client/lib/*")
    q = shlex.quote
    sources = [ROOT / "sniffer/java" / (name + ".java") for name in EXPORTERS]
    return [
        "javac -cp "
        + q(str(ROOT / "client/lib/*"))
        + " -d "
        + q(str(classes))
        + " "
        + " ".join(q(str(path)) for path in sources),
        "java -Xmx2g -cp "
        + q(classpath)
        + " ExportGrantedSpellEffectTrees "
        + q(str(output / "all-spell-refs.txt"))
        + " "
        + q(str(output / "all-spells")),
        "python3 "
        + q(str(ROOT / "server/tools/convert_spell_effect_trees.py"))
        + " "
        + q(str(output / "all-spells"))
        + " "
        + q(str(output / "all-spell-effect-trees.json")),
        "java -Xmx2g -cp "
        + q(classpath)
        + " ExportCombatStates "
        + q(str(output / "all-states")),
        "python3 "
        + q(str(ROOT / "server/tools/convert_combat_states.py"))
        + " "
        + q(str(output / "all-states"))
        + " "
        + q(str(output / "all-combat-state-definitions.json")),
        "java -Xmx2g -cp "
        + q(classpath)
        + " ExportEffectAreaTrees "
        + q(str(output / "all-area-effects.tsv")),
        "java -Xmx2g -cp "
        + q(classpath)
        + " ExportNativeEffectAreas "
        + q(str(output / "all-native-effect-areas.json")),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime/combat-review-20261007/bulk-staging",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Inspect only; default behavior"
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Write references, inspection, and command plan in a new staging directory; never execute exporters",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    runtime = (ROOT / ".runtime").resolve()
    if runtime not in output.parents or output == runtime:
        parser.error("Output must be a new directory beneath repository .runtime")
    if args.prepare and args.dry_run:
        parser.error("--prepare and --dry-run are mutually exclusive")
    report, refs = inspect()
    report.update(
        {
            "mode": "prepare" if args.prepare else "dry-run",
            "imported": False,
            "repository_cwd": str(ROOT),
            "export_commands": plan(output),
        }
    )
    report["client_sources"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [
            ROOT / "client/lib/wakfu-client.jar",
            *sorted((ROOT / "client/contents/bdata").glob("*.jar")),
        ]
    }
    report["exporter_sources"] = {
        name: hashlib.sha256(
            (ROOT / "sniffer/java" / (name + ".java")).read_bytes()
        ).hexdigest()
        for name in EXPORTERS
    }
    if args.prepare:
        output.mkdir(parents=True, exist_ok=False)
        (output / "classes").mkdir()
        (output / "all-spell-refs.txt").write_text("\n".join(map(str, refs)) + "\n")
        (output / "inspection.json").write_text(json.dumps(report, indent=2) + "\n")
        (output / "export-plan.sh").write_text(
            "#!/bin/sh\nset -eu\ncd "
            + shlex.quote(str(ROOT))
            + "\n"
            + "\n".join(report["export_commands"])
            + "\n"
        )
    print(
        json.dumps(
            {
                "mode": report["mode"],
                "imported": False,
                "casting_references": len(refs),
                "covered_spell_ids": report["covered_spell_ids"],
                "missing_spell_tree_count": len(report["missing_spell_tree_ids"]),
                "unresolved_local_child_counts": {
                    k: len(v) for k, v in report["unresolved_local_children"].items()
                },
                "output": str(output) if args.prepare else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
