"""Inventory scoped captured-class structural dependencies without importing NPC gameplay."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "server/protocol/native-class-captured-profiles.json"
GRAPH = ROOT / ".runtime/combat-review-20261007/class-closure-compact-graph.json"
OUTPUT = (
    ROOT
    / "docs/reports/combat-inventory/class-captured-dependency-inventory-20261007.json"
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    before = {
        str(p.relative_to(ROOT)): digest(p) for p in (PROFILES, GRAPH, Path(__file__))
    }
    profiles = json.loads(PROFILES.read_text())["profiles"]
    graph = json.loads(GRAPH.read_text())
    reached = set()
    edges = []
    missing = []
    unknown_scaled = []
    nested_profiles = {}
    pending = []
    for profile_id, profile in profiles.items():
        for ability in profile["abilities"]:
            node = ("spells", str(ability["reference"]))
            pending.append(node)
            edges.append(
                {
                    "source": f"captured-profile:{profile_id}",
                    "target": f"spell:{node[1]}",
                    "kind": "native_own_book",
                    "class_id": 2,
                }
            )
        for state_id in profile["initial_state_triples"][::3]:
            pending.append(("states", str(state_id)))
            edges.append(
                {
                    "source": f"captured-profile:{profile_id}",
                    "target": f"state:{state_id}",
                    "kind": "native_initial_state",
                    "class_id": 2,
                }
            )
    singular = {
        "spells": "spell",
        "states": "state",
        "areas": "area",
        "effects": "effect",
    }
    while pending:
        kind, reference = pending.pop()
        if (kind, reference) in reached:
            continue
        reached.add((kind, reference))
        record = graph[kind].get(reference)
        if record is None:
            missing.append([kind, reference])
            continue
        owner = f"{singular[kind]}:{reference}"
        if kind != "effects":
            for child in record:
                pending.append(("effects", str(child)))
                edges.append(
                    {
                        "source": owner,
                        "target": f"effect:{child}",
                        "kind": "legacy_native_root",
                        "class_id": 2,
                    }
                )
            continue
        family, children, references, slope = record[:4]
        for child in children:
            pending.append(("effects", str(child)))
            edges.append(
                {
                    "source": owner,
                    "target": f"effect:{child}",
                    "kind": "ordered_group_child",
                    "class_id": 2,
                }
            )
        target = {304: "states", 315: "areas", 649: "spells"}.get(family)
        if target:
            if slope:
                unknown_scaled.append(reference)
            for child in references:
                pending.append((target, str(child)))
                edges.append(
                    {
                        "source": owner,
                        "target": f"{singular[target]}:{child}",
                        "kind": f"legacy_reference_family{family}",
                        "class_id": 2,
                    }
                )
        if family == 307:
            nested_profiles[reference] = references
            for child in references:
                edges.append(
                    {
                        "source": owner,
                        "target": f"pending-summon-profile:{child}",
                        "kind": "native307_profile_dependency",
                        "class_id": 2,
                    }
                )
    after = {name: digest(ROOT / name) for name in before}
    if before != after:
        raise ValueError("Captured dependency inventory inputs changed")
    return {
        "schema": "class-captured-dependency-inventory-v1",
        "class_id": 2,
        "scope": "Original class-capture domain; dependencies only, no standalone NPC spell gameplay",
        "source_sha256": before,
        "source_stable": True,
        "profile_count": len(profiles),
        "node_references": {
            kind: sorted(int(r) for k, r in reached if k == kind) for kind in singular
        },
        "edges": edges,
        "missing_legacy_records": missing,
        "unknown_scaled_legacy_references": unknown_scaled,
        "nested_summon_effect_profiles": nested_profiles,
        "pending_profile_ids": sorted(
            {r for refs in nested_profiles.values() for r in refs}
        ),
        "limitations": [
            "Compact reference traversal covers only304/315/649; modern dynamic reference contracts remain pending",
            "Native level-zero root/parameter samples are not supplied by this inventory",
            "Nested summon profile books/initial states remain pending original export",
            "Dependency reference is not proof of execution reachability or client functionality",
        ],
        "runtime_verified": False,
        "complete_typed_closure": False,
    }


if __name__ == "__main__":
    document = build()
    OUTPUT.write_text(json.dumps(document, separators=(",", ":")) + "\n")
    print(
        json.dumps(
            {
                "counts": {k: len(v) for k, v in document["node_references"].items()},
                "pending_profiles": document["pending_profile_ids"],
                "source_stable": True,
            }
        )
    )
