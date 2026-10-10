#!/usr/bin/env python3
"""Index every preserved native dependency for the thirteen remaining classes.

This is an inventory, never gameplay accreditation. Raw native definitions stay
in the hash-pinned source graph; this index preserves identities and typed edges.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/reports/combat-inventory"
OUT = BASE / "remaining-classes-20261010"
ACCEPTED = {2, 7, 8, 9, 11}


def load(name):
    return json.loads((BASE / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    graph = load("class-native-mechanic-graph-20261007.json")
    components = load("class-native-mechanic-components-20261007.json")
    inventory = load("inventory.json")
    routes = load("class-effect-route-inventory-20261010.json")
    requirements = load("class-mechanic-requirements-20261007.json")
    labels = {f"state:{r['id']}": r.get("name") for r in inventory["states"]}
    labels.update(
        {
            f"spell:{r['id']}": r.get("name")
            for r in inventory["spells"] + inventory["extra_spells"]
        }
    )
    family_routes = {r["family"]: r for r in routes["families"]}
    adjacency = {}
    for edge in graph["edges"]:
        adjacency.setdefault(edge["source"], []).append(edge)
    sources = {
        name: sha(BASE / name)
        for name in (
            "class-native-mechanic-graph-20261007.json",
            "class-native-mechanic-components-20261007.json",
            "inventory.json",
            "class-effect-route-inventory-20261010.json",
            "class-mechanic-requirements-20261007.json",
        )
    }
    summary = []
    for cls in components["classes"]:
        breed = cls["breed"]
        if breed in ACCEPTED:
            continue
        membership = {}
        for scope in ("spell_dependency_components", "innate_dependency_components"):
            for keys in cls[scope].values():
                for key in keys:
                    membership.setdefault(key, []).append(scope)
        nodes = {}
        for key, scopes in sorted(membership.items()):
            native = graph["nodes"].get(key)
            row = {
                "identity": key,
                "scopes": scopes,
                "label": labels.get(key),
                "source_definition_present": native is not None,
                "behavior_verification": "unverified",
            }
            if native:
                for field in (
                    "kind",
                    "reference",
                    "family",
                    "native_missing",
                    "native_export_exception",
                    "criterion_raw",
                    "native_runner_class",
                    "raw_parameters",
                    "subscription",
                    "event_target_code",
                    "event_caster_code",
                    "event_priority",
                    "event_execution_count",
                    "owner_on_caster",
                    "reverse_subscription",
                    "global_subscription",
                    "minimum_level",
                    "maximum_level",
                    "native_ability_profile",
                    "native_type",
                    "entry_masks",
                    "exit_masks",
                    "removal_masks",
                    "area_properties",
                    "reference_semantics",
                ):
                    if field in native:
                        row[field] = native[field]
                if "family" in native:
                    route = family_routes.get(native["family"])
                    row["runtime_route"] = (
                        {k: route[k] for k in ("status", "bindings")}
                        if route
                        else {"status": "not_in_route_matrix"}
                    )
            nodes[key] = row
        edges = [edge for key in membership for edge in adjacency.get(key, [])]
        external = sorted({e["target"] for e in edges} - membership.keys())
        owned = [r for r in inventory["spells"] if r["breed"] == breed]
        extras = [r for r in inventory["extra_spells"] if breed in r.get("breeds", [])]
        units = []
        for requirement in requirements["units"]:
            affected = requirement.get("affected_class_nodes", {}).get(str(breed))
            if affected is not None:
                unit = {
                    key: requirement.get(key)
                    for key in (
                        "id",
                        "category",
                        "contract",
                        "status",
                        "status_reason",
                        "dynamic_reachability",
                    )
                }
                unit["class_nodes"] = affected
                units.append(unit)
        data = {
            "schema": 1,
            "breed": breed,
            "native_class_name": cls["native_class_name"],
            "source_sha256": sources,
            "published_catalog_revision": routes["published_catalog_revision"],
            "owned_spells": owned,
            "extra_spells": extras,
            "innate_seed_states": cls["innate_seed_states"],
            "nodes": nodes,
            "typed_edges": edges,
            "external_edge_targets": external,
            "mechanic_requirement_units": units,
            "unknown_native_definitions": cls["unknown_native_definitions"],
            "limits": [
                "Native graph is a dated structural export, not dynamic reachability.",
                "Synthetic condition/mask/HMI nodes need no spell/state definition.",
                "Unclassified reference producers and temporary/copy profiles require the review report.",
                "Published runtime routes are current; functional and client verification remain separate.",
            ],
        }
        output = OUT / f"{breed}-inventory.json"
        output.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        summary.append(
            {
                "breed": breed,
                "name": cls["native_class_name"],
                "owned": dict(Counter(r["kind"] for r in owned)),
                "extra_spells": len(extras),
                "typed_counts": dict(Counter(k.split(":", 1)[0] for k in membership)),
                "external_edge_targets": len(external),
                "requirement_units": len(units),
                "inventory_sha256": sha(output),
            }
        )
    assert len(summary) == 13
    for name, digest in sources.items():
        assert sha(BASE / name) == digest, f"Source changed during inventory: {name}"
    (OUT / "index.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "classes": summary,
                "sources_stable": True,
                "source_sha256": sources,
                "accepted_class_count": 5,
                "inventory_class_count": 13,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "classes": len(summary),
                "owned_spells": sum(sum(r["owned"].values()) for r in summary),
                "extra_spells": sum(r["extra_spells"] for r in summary),
            }
        )
    )


if __name__ == "__main__":
    main()
