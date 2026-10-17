#!/usr/bin/env python3
"""Inventory class dependency closure without importing the combat runtime.

Routes are source registrations, never semantic or client accreditation.
The compact graph is a staged structural snapshot, not dynamic reachability.
"""
import argparse
import ast
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from build_spell_inventory import literal_handler_families
from combat_operation_sources import operation_source_paths

sys.path.insert(0, str(ROOT / "server"))
from wakfu_server.combat_operation_registry import dependency_specs


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declared(path, name):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return set(ast.literal_eval(node.value))
    raise ValueError(f"Missing declaration {name}")


def dispatch_routes(path):
    routes = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        left = node.left
        if not (
            isinstance(left, ast.Subscript)
            and isinstance(left.slice, ast.Constant)
            and left.slice.value == "effect_class"
        ):
            continue
        try:
            value = ast.literal_eval(node.comparators[0])
        except (ValueError, TypeError):
            continue
        if isinstance(node.ops[0], ast.Eq) and type(value) is int:
            routes.add(value)
        elif isinstance(node.ops[0], ast.In) and isinstance(value, (tuple, list, set)):
            routes.update(item for item in value if type(item) is int)
    return routes


def build(graph, ledger, innate, routes, profiles=None):
    effects = graph["effects"]
    rows = []
    for spell in ledger["spells"]:
        pending = [("spell", spell["spell_id"])]
        pending += [
            ("state", entry["reference"])
            for breed in innate["breeds"]
            if breed["breed"] in spell["breeds"]
            for entry in breed["innate_states"]
        ]
        seen = defaultdict(set)
        unresolved = defaultdict(set)
        while pending:
            kind, identity = pending.pop()
            if identity in seen[kind]:
                continue
            seen[kind].add(identity)
            if kind == "summon":
                profile = (profiles or {}).get(str(identity))
                if profile is None:
                    unresolved[kind].add(identity)
                else:
                    pending += [
                        ("spell", ability["reference"])
                        for ability in profile["abilities"]
                    ]
                continue
            key = str(identity)
            table = effects if kind == "effect" else graph[kind + "s"]
            if key not in table:
                unresolved[kind].add(identity)
                continue
            if kind != "effect":
                pending += [("effect", value) for value in table[key]]
                continue
            family, children, references = table[key][:3]
            pending += [("effect", value) for value in children]
            for spec in dependency_specs(family):
                values = references
                if spec.fixed_reference is not None:
                    values = (spec.fixed_reference,)
                if spec.transform == "signed-short":
                    values = [((value + 32768) % 65536) - 32768 for value in values]
                if spec.relation == "removes":
                    # A removal is an identity dependency, never execution of
                    # the removed state's effect tree.
                    seen["removed_state"].update(values)
                else:
                    pending += [(spec.kind, value) for value in values]
        families = sorted(
            {
                effects[str(value)][0]
                for value in seen["effect"]
                if str(value) in effects
            }
        )
        criteria = sorted(
            {graph["criteria"].get(str(value), "") for value in seen["effect"]} - {""}
        )
        conditions = sorted(
            {
                name
                for criterion in criteria
                for name in re.findall(r"\b([A-Za-z_]\w*)\s*\(", criterion)
            }
        )
        row = {
            key: spell[key] for key in ("spell_id", "name", "kind", "origin", "breeds")
        }
        row.update(
            dependencies={
                kind: sorted(values) for kind, values in sorted(seen.items())
            },
            unresolved_structural_references={
                kind: sorted(values) for kind, values in sorted(unresolved.items())
            },
            effect_families=families,
            criterion_functions=conditions,
            criterion_expression_count=len(criteria),
            registered_route_families=sorted(set(families) & routes),
            unregistered_route_families=sorted(set(families) - routes),
            condition_contracts="unknown",
            event_contracts="unknown",
            class_mechanic_semantics="unknown",
            area_lifecycle="unknown"
            if seen["area"]
            else "not_observed_in_classified_graph",
            summon_lifecycle="unknown"
            if seen["summon"]
            else "not_observed_in_classified_graph",
            complete_semantic_verification="unknown",
            complete_client_verification="unknown",
            historical_ledger_claims={
                key: spell.get(key)
                for key in (
                    "catalog_imported",
                    "semantic_verified",
                    "client_verified",
                    "offline_execution",
                )
            },
        )
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "agents_docs/reports/combat-inventory/class-dependency-coverage-20261007",
    )
    args = parser.parse_args()
    graph_path = (
        ROOT / ".runtime/combat-review-20261007/class-closure-compact-graph.json"
    )
    ledger_path = (
        ROOT / "agents_docs/reports/combat-inventory/verification-ledger-20261007.json"
    )
    innate_path = ROOT / "server/protocol/breed-innate-definitions.json"
    runtime_path = ROOT / "server/wakfu_server/combat/combat_effect_runtime.py"
    registry_path = ROOT / "server/protocol/effect-characteristic-registry.json"
    damage_path = ROOT / "server/wakfu_server/combat/combat_damage_contracts.py"
    displacement_path = (
        ROOT / "server/wakfu_server/combat/combat_displacement_geometry.py"
    )
    dispatch_path = ROOT / "server/wakfu_server/combat/combat_effect_dispatch.py"
    profiles_path = ROOT / "server/protocol/native-class-summon-abilities.json"
    summon_closure_path = (
        ROOT / "server/protocol/native-class-summon-effect-closure.json"
    )
    paths = [
        *operation_source_paths(),
        profiles_path,
        summon_closure_path,
        dispatch_path,
        graph_path,
        ledger_path,
        innate_path,
        runtime_path,
        registry_path,
        damage_path,
        displacement_path,
        Path(__file__),
    ]
    before = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    routes = literal_handler_families(ast.parse(runtime_path.read_text()))
    routes |= (
        declared(damage_path, "DAMAGE_FAMILIES")
        | declared(damage_path, "HEAL_ELEMENTS")
        | declared(displacement_path, "FAMILIES")
    )
    routes |= set(map(int, load(registry_path)["effects"]))
    routes |= dispatch_routes(dispatch_path)
    profiles = load(profiles_path)["profiles"]
    summon_closure = load(summon_closure_path)
    rows = build(
        load(graph_path), load(ledger_path), load(innate_path), routes, profiles
    )
    families = defaultdict(list)
    conditions = defaultdict(list)
    classes = defaultdict(Counter)
    for row in rows:
        for family in row["effect_families"]:
            families[family].append(row["spell_id"])
        for condition in row["criterion_functions"]:
            conditions[condition].append(row["spell_id"])
        for breed in row["breeds"]:
            classes[breed][row["origin"]] += 1
            classes[breed]["with_unregistered_route"] += bool(
                row["unregistered_route_families"]
            )
    after = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    data = {
        "schema": 1,
        "scope": "813 class spells/extras plus owning class innates and published class-referenced summon abilities; classified staged graph only",
        "sources_before": before,
        "sources_after": after,
        "sources_stable": before == after,
        "published_summon_dependencies": {
            "profiles": len(profiles),
            "ability_records": sum(len(p["abilities"]) for p in profiles.values()),
            "unique_abilities": len(summon_closure["ability_reference_closure"]),
            "effect_closure": len(summon_closure["effect_reference_closure"]),
            "imported_effects": len(summon_closure["added_effect_ids"]),
        },
        "summary": {
            "spells": len(rows),
            "classes": len(classes),
            "effect_families": len(families),
            "criterion_functions": len(conditions),
            "with_unregistered_family_route": sum(
                bool(r["unregistered_route_families"]) for r in rows
            ),
            "fully_semantic_verified": None,
            "fully_client_verified": None,
            "functional_completion_percent": None,
        },
        "limitations": [
            "Graph snapshot follows group children and 304/state,308+314+315+339/area,649/grant,307/summon references only.",
            "Includes all sampled branches; native false guards remain structural edges.",
            "Family registration may require configuration/authority and does not prove successful execution.",
            "Criteria names are dependencies, not implementation or correctness proofs.",
            "Events, timing, target selectors, reference producers outside classified families and class mechanics require richer native exports.",
            "Only published class-referenced summon ability books are followed; no general monster integration.",
            "Historical ledger claims are not refreshed or accredited here.",
            "No numerical functional completion percentage can be derived from these observations.",
        ],
        "classes": {str(k): dict(v) for k, v in sorted(classes.items())},
        "family_dependents": {
            str(k): {"registered_route": k in routes, "spell_ids": v}
            for k, v in sorted(families.items())
        },
        "condition_dependents": dict(sorted(conditions.items())),
        "spells": rows,
    }
    args.output.with_suffix(".json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    )
    with args.output.with_suffix(".csv").open("w", newline="") as stream:
        columns = [
            "spell_id",
            "name",
            "kind",
            "origin",
            "breeds",
            "effect_families",
            "unregistered_route_families",
            "criterion_functions",
            "complete_semantic_verification",
            "complete_client_verification",
        ]
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (list, dict))
                    else value
                    for key, value in row.items()
                }
            )
    print(json.dumps(data["summary"]))


if __name__ == "__main__":
    main()
