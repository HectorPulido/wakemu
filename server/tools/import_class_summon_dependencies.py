"""Import only native ability dependencies of class-referenced summons, offline."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "server/protocol"
STAGE = ROOT / ".runtime/combat-review-20261007/bulk-staging"
REVIEW = ROOT / ".runtime/combat-review-20261007"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entries(path, section):
    """Read one dictionary section without materializing an entire native catalog."""
    opener = open
    decoder = json.JSONDecoder()
    with opener(path, "rt") as stream:
        buffer = ""
        marker = re.compile('"' + re.escape(section) + r'"\s*:\s*\{')
        while True:
            chunk = stream.read(262144)
            if not chunk:
                raise ValueError(f"Missing section {section}: {path}")
            buffer += chunk
            match = marker.search(buffer)
            if match:
                buffer = buffer[match.end() :]
                break
            buffer = buffer[-128:]
        while True:
            buffer = buffer.lstrip(" \t\r\n,")
            if not buffer:
                buffer = stream.read(262144)
                if not buffer:
                    raise ValueError("Truncated catalog")
                continue
            if buffer[0] == "}":
                return
            try:
                key, offset = decoder.raw_decode(buffer)
                rest = buffer[offset:].lstrip()
                if not rest or rest[0] != ":":
                    raise json.JSONDecodeError("Incomplete entry", buffer, offset)
                rest = rest[1:].lstrip()
                value, end = decoder.raw_decode(rest)
            except json.JSONDecodeError:
                chunk = stream.read(262144)
                if not chunk:
                    raise
                buffer += chunk
                continue
            yield key, value
            buffer = rest[end:]


def select(path, section, wanted):
    return {key: value for key, value in entries(path, section) if key in wanted}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    profile_path = DATA / "native-class-summon-abilities.json"
    graph_path = REVIEW / "class-closure-compact-graph.json"
    graph = json.loads(graph_path.read_text())
    profiles = json.loads(profile_path.read_text())["profiles"]
    seeds = {str(a["reference"]) for p in profiles.values() for a in p["abilities"]}
    reached = {kind: set() for kind in ("spells", "states", "areas", "effects")}
    zero_path = (
        REVIEW / "controlled-summon-proof/level-zero/native-summon-ability-zero.json"
    )
    zero = json.loads(zero_path.read_text())
    pending = [("spells", ref) for ref in seeds]
    pending.extend(("effects", ref) for ref in zero["effects"])
    missing = []
    scaled = []
    while pending:
        kind, ref = pending.pop()
        if ref in reached[kind]:
            continue
        reached[kind].add(ref)
        record = graph[kind].get(ref)
        if record is None:
            missing.append([kind, ref])
            continue
        if kind != "effects":
            pending.extend(("effects", str(child)) for child in record)
            continue
        family, children, references, slope = record[:4]
        pending.extend(("effects", str(child)) for child in children)
        target = {304: "states", 315: "areas", 649: "spells"}.get(family)
        if target:
            if slope:
                scaled.append(ref)
            pending.extend((target, str(child)) for child in references)
        if family == 307:
            raise ValueError(
                "Nested summon dependencies require explicit class profile evidence"
            )
    if missing or scaled:
        raise ValueError(f"Unclosed structural references: {missing}; scaled: {scaled}")
    target_path = DATA / "granted-spell-effect-trees.json"
    source_paths = [
        profile_path,
        graph_path,
        target_path,
        STAGE / "all-spell-effect-trees.json",
        STAGE / "all-combat-state-definitions.json",
        STAGE / "all-area-effect-trees.json",
        DATA / "spell-effect-trees.json",
        DATA / "combat-state-definitions.json",
        DATA / "native-area-effect-trees.json",
        DATA / "native-effect-areas.json",
        DATA / "native-spell-casting.json",
        REVIEW / "controlled-summon-proof/manifest.json",
        zero_path,
        REVIEW / "class-summon-import/native-summon.json",
        REVIEW / "class-summon-import/runtime-metadata.json",
        ROOT / "sniffer/java/ExportClassSummonEffectTrees.java",
        ROOT / "sniffer/java/ExportEffectRuntimeMetadata.java",
    ]
    native_manifest = json.loads(
        (REVIEW / "controlled-summon-proof/manifest.json").read_text()
    )
    native_sources = {
        name: expected
        for name, expected in native_manifest["source_hashes"].items()
        if name.startswith("client/")
    }
    for name, expected in native_sources.items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Native provenance changed: {name}")
    source_paths.extend(ROOT / name for name in native_sources)
    source_paths.extend(
        [
            ROOT / "server/tools/import_class_summon_dependencies.py",
            ROOT / "server/tools/convert_spell_effect_trees.py",
        ]
    )
    before = {str(p.relative_to(ROOT)): digest(p) for p in source_paths}
    target = json.loads(target_path.read_bytes())
    local_spells = select(DATA / "spell-effect-trees.json", "spells", reached["spells"])
    local_spells.update(
        {k: v for k, v in target["spells"].items() if k in reached["spells"]}
    )
    local_effects = {}
    existing_conflicts = []
    for path in [
        DATA / "spell-effect-trees.json",
        target_path,
        DATA / "combat-state-definitions.json",
        DATA / "native-area-effect-trees.json",
    ]:
        for ref, value in select(path, "effects", reached["effects"]).items():
            if ref in local_effects and value != local_effects[ref]:
                existing_conflicts.append(
                    {
                        "reference": ref,
                        "path": str(path.relative_to(ROOT)),
                        "fields": sorted(
                            k
                            for k in set(value) | set(local_effects[ref])
                            if value.get(k) != local_effects[ref].get(k)
                        ),
                    }
                )
            else:
                local_effects[ref] = value
    staged_spells = select(
        STAGE / "all-spell-effect-trees.json", "spells", reached["spells"]
    )
    staged_effects = {}
    staged_conflicts = []
    for path in [
        STAGE / "all-spell-effect-trees.json",
        STAGE / "all-combat-state-definitions.json",
        STAGE / "all-area-effect-trees.json",
    ]:
        for ref, value in select(path, "effects", reached["effects"]).items():
            if ref in staged_effects and staged_effects[ref] != value:
                staged_conflicts.append(ref)
            else:
                staged_effects[ref] = value
    fresh = json.loads((REVIEW / "class-summon-import/native-summon.json").read_text())
    runtime_metadata = json.loads(
        (REVIEW / "class-summon-import/runtime-metadata.json").read_text()
    )
    staged_spells.update(fresh["spells"])
    staged_effects.update(fresh["effects"])
    for ref, effect in staged_effects.items():
        effect.update(runtime_metadata[ref])
    if staged_conflicts:
        raise ValueError(f"Staged exact conflicts: {staged_conflicts}")
    for ref, value in staged_effects.items():
        classified = graph["effects"][ref]
        if value["effect_class"] != classified[0] or set(value["children"]) != set(
            classified[1]
        ):
            raise ValueError(f"Compact graph identity changed: {ref}")
    differences = []
    core_fields = (
        "effect_class",
        "parameters",
        "children",
        "variant",
        "minimum_level",
        "maximum_level",
        "criteria",
        "target_masks",
        "native_target_selector",
        "native_effect_flags",
        "native_localization_enabled",
    )
    for ref in local_effects:
        value = staged_effects[ref]
        if any(value.get(k) != local_effects[ref].get(k) for k in core_fields):
            raise ValueError(
                f"Native dependency identity conflicts with local definition: {ref}"
            )
        fields = sorted(
            k
            for k in set(value) | set(local_effects[ref])
            if value.get(k) != local_effects[ref].get(k)
        )
        if fields:
            differences.append({"reference": ref, "fields": fields})
    missing_spells = reached["spells"] - local_spells.keys()
    missing_effects = reached["effects"] - local_effects.keys()
    casting = select(DATA / "native-spell-casting.json", "spells", reached["spells"])
    if (
        reached["spells"] != staged_spells.keys()
        or reached["effects"] != staged_effects.keys()
    ):
        raise ValueError("Staged dependency definitions unavailable")
    for ref in missing_spells:
        record = staged_spells[ref]
        for field in ("line_of_sight", "linear", "free_cell"):
            record[field] = casting[ref][field]
        target["spells"][ref] = record
    target["effects"].update({ref: staged_effects[ref] for ref in missing_effects})
    local_states = select(
        DATA / "combat-state-definitions.json", "states", reached["states"]
    )
    local_areas = select(DATA / "native-effect-areas.json", "areas", reached["areas"])
    if (
        reached["states"] != local_states.keys()
        or reached["areas"] != local_areas.keys()
    ):
        raise ValueError(
            "Missing state or area definition in production dependency catalog"
        )
    after_read = {str(p.relative_to(ROOT)): digest(p) for p in source_paths}
    if before != after_read:
        raise ValueError("Import source changed while reading")
    report = {
        "scope": "Class-referenced summon abilities only; structural closure, not gameplay certification",
        "profile_count": len(profiles),
        "ability_seed_count": len(seeds),
        "closure_counts": {k: len(v) for k, v in reached.items()},
        "added_spell_ids": sorted(map(int, missing_spells)),
        "added_effect_ids": sorted(map(int, missing_effects)),
        "existing_local_exact_conflicts": existing_conflicts,
        "existing_stage_differences_preserved": differences,
        "sources_stable": True,
        "source_sha256": before,
        "native_client_source_count": len(native_sources),
        "published": args.publish,
        "native_zero_effect_count": len(zero["effects"]),
        "fresh_native_tree_count": len(fresh["spells"]),
        "fresh_native_effect_count": len(fresh["effects"]),
        "native_runtime_metadata_count": len(runtime_metadata),
        "limitations": [
            "Reference traversal classifies only group children and families304/315/649.",
            "Criteria, implicit references, native event producers and gameplay correctness require separate validation.",
            "Native level-zero casting snapshot for new ability references requires its separate native export.",
        ],
    }
    if args.publish:
        backup = REVIEW / "class-summon-import/granted-spell-effect-trees.before.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            backup.write_bytes(target_path.read_bytes())
        target.setdefault("provenance", {})["class_summon_dependency_import"] = {
            "source_sha256": before,
            "spell_ids": report["added_spell_ids"],
            "effect_ids": report["added_effect_ids"],
            "scope": report["scope"],
        }
        temporary = target_path.with_name(target_path.name + ".class-summon-import.tmp")
        temporary.write_bytes(json.dumps(target, separators=(",", ":")).encode())
        if digest(target_path) != before[str(target_path.relative_to(ROOT))]:
            temporary.unlink()
            raise ValueError("Target catalog changed before replacement")
        temporary.replace(target_path)
        report["output_sha256"] = digest(target_path)
    report_path = (
        ROOT
        / "docs/reports/combat-inventory/class-summon-dependency-import-20261007.json"
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "profile_count",
                    "ability_seed_count",
                    "closure_counts",
                    "sources_stable",
                    "published",
                ]
            }
        )
    )
    print(
        "Added trees:",
        len(missing_spells),
        "effects:",
        len(missing_effects),
        "existing staged field differences:",
        len(differences),
        "local conflicts:",
        len(existing_conflicts),
    )


if __name__ == "__main__":
    main()
