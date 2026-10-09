#!/usr/bin/env python3
"""Scope native family307 descriptor exports from class roots and innates."""
import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    review = root / ".runtime/combat-review-20261007"
    paths = {
        "graph": review / "class-closure-compact-graph.json",
        "class_references": review / "level-zero/class-references.txt",
        "innates": root / "server/protocol/breed-innate-definitions.json",
        "zero": root / "server/protocol/native-class-spell-level-zero.json",
        "profiles": root / "server/protocol/native-class-summon-abilities.json",
    }
    before = {str(path.relative_to(root)): sha256(path) for path in paths.values()}
    graph = json.loads(paths["graph"].read_text())
    spells = paths["class_references"].read_text().splitlines()
    breeds = json.loads(paths["innates"].read_text())["breeds"]
    with open(paths["zero"], "rt") as stream:
        zero = json.load(stream)
    pending = [("spells", reference) for reference in spells]
    pending.extend(
        ("states", str(state["reference"]))
        for breed in breeds
        for state in breed["innate_states"]
    )
    pending.extend(
        ("effects", str(effect))
        for reference in spells
        for effect in zero["spells"][reference][2]
    )
    reached = {kind: set() for kind in ("spells", "states", "areas", "effects")}
    parents = {}
    descriptors = {}
    missing = []
    while pending:
        kind, reference = pending.pop()
        if reference in reached[kind]:
            continue
        reached[kind].add(reference)
        record = graph[kind].get(reference)
        if record is None:
            missing.append([kind, reference])
            continue
        edges = []
        if kind == "effects":
            family, children, targets, scaled = record[:4]
            edges.extend(("effects", str(child)) for child in children)
            target_kind = {304: "states", 315: "areas", 649: "spells"}.get(family)
            if target_kind is not None:
                edges.extend((target_kind, str(target)) for target in targets)
            if family == 307:
                descriptors[reference] = dict(
                    structural_profile_references=targets,
                    structural_profile_reference_scaled=scaled,
                    structural_record=record,
                    criteria=graph["criteria"].get(reference),
                    source_domains=graph["source_domains"].get(reference),
                )
        else:
            edges.extend(("effects", str(effect)) for effect in record)
        for child_kind, child in edges:
            parents.setdefault(f"{child_kind}:{child}", set()).add(
                f"{kind}:{reference}"
            )
            pending.append((child_kind, child))
    profiles = {
        int(reference)
        for reference in json.loads(paths["profiles"].read_text())["profiles"]
    }
    linked = {
        profile
        for descriptor in descriptors.values()
        for profile in descriptor["structural_profile_references"]
    }
    after = {str(path.relative_to(root)): sha256(path) for path in paths.values()}
    if before != after:
        raise ValueError("Class descriptor scope sources changed during inventory")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "effect-references.txt").write_text(
        "\n".join(sorted(descriptors, key=int)) + "\n"
    )
    report = dict(
        scope="Class spell/extras roots and breed innates; nested state/area/grant references; no monster roots",
        class_seed_count=len(spells),
        counts={kind: len(values) for kind, values in reached.items()},
        descriptor_effect_count=len(descriptors),
        scoped_profile_count=len(profiles),
        structurally_linked_profiles=sorted(linked),
        profile_scope_matches=linked == profiles,
        unresolved_structural_nodes=missing,
        descriptors=descriptors,
        parents={key: sorted(values) for key, values in parents.items()},
        source_sha256=before,
        sources_stable=True,
        limitations=[
            "Structural criteria are preserved, not asserted true.",
            "Descriptor execution and owner/control lifecycle require native export and actual context.",
            "Profile references in the old graph are seeds, not complete parameter contracts.",
        ],
    )
    (args.output / "descriptor-scope.json").write_text(
        json.dumps(report, separators=(",", ":")) + "\n"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "class_seed_count",
                    "counts",
                    "descriptor_effect_count",
                    "scoped_profile_count",
                    "profile_scope_matches",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
