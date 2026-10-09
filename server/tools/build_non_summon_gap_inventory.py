"""Measure registered class effect routes, separately from semantic completion."""
import argparse
import ast
from collections import defaultdict
import csv
import hashlib
import re
import json
from pathlib import Path

import build_class_dependency_inventory as inventory

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = {307, 324, 325}


def build(output):
    relative_paths = [
        "docs/reports/combat-inventory/class-native-mechanic-graph-20261007.json",
        "docs/reports/combat-inventory/verification-ledger-20261007.json",
        "server/protocol/breed-innate-definitions.json",
        "server/protocol/effect-characteristic-registry.json",
        "server/wakfu_server/combat/combat_effect_runtime.py",
        "server/wakfu_server/combat/combat_damage_healing.py",
        "server/wakfu_server/combat/combat_displacement.py",
        "server/wakfu_server/combat/combat_effect_dispatch.py",
        "server/tools/build_class_dependency_inventory.py",
        "server/tools/build_spell_inventory.py",
        "server/tools/build_non_summon_gap_inventory.py",
    ]
    raw = {name: (ROOT / name).read_bytes() for name in relative_paths}
    digests = {name: hashlib.sha256(value).hexdigest() for name, value in raw.items()}
    graph = json.loads(raw[relative_paths[0]])
    ledger = json.loads(raw[relative_paths[1]])
    innates = json.loads(raw[relative_paths[2]])
    routes = inventory.literal_handler_families(ast.parse(raw[relative_paths[4]]))
    for filename, declaration in (
        (relative_paths[5], "DAMAGE_FAMILIES"),
        (relative_paths[5], "HEAL_ELEMENTS"),
        (relative_paths[6], "FAMILIES"),
    ):
        for node in ast.walk(ast.parse(raw[filename])):
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == declaration
                for target in node.targets
            ):
                routes.update(ast.literal_eval(node.value))
                break
        else:
            raise ValueError("Missing route declaration: " + declaration)
    routes.update(map(int, json.loads(raw[relative_paths[3]])["effects"]))
    routes.update(inventory.dispatch_routes(ROOT / relative_paths[7]))
    # Traverse native typed roots and references. Creature books are excluded;
    # definition masks, conditions and HMI nodes are evidence, not execution.
    adjacency = defaultdict(list)
    for edge in graph["edges"]:
        if edge["kind"] == "native_profile_ability":
            continue
        if edge["kind"] == "native_parameter_reference":
            source = graph["nodes"][edge["source"]]
            if source.get("family") in EXCLUDED or edge["target"].startswith(
                "profile:"
            ):
                continue
        levels = edge.get("sample_levels")
        if levels is not None and not any(0 <= level <= 245 for level in levels):
            continue
        adjacency[edge["source"]].append(edge["target"])
    dependents = defaultdict(list)
    conditions = defaultdict(list)
    dependencies = defaultdict(set)
    for spell in ledger["spells"]:
        seeds = ["spell:" + str(spell["spell_id"])]
        seeds.extend(
            "state:" + str(state["reference"])
            for breed in innates["breeds"]
            if breed["breed"] in spell["breeds"]
            for state in breed["innate_states"]
        )
        seen = set()
        while seeds:
            key = seeds.pop()
            if key in seen:
                continue
            seen.add(key)
            seeds.extend(adjacency.get(key, ()))
        seen_families, seen_conditions = set(), set()
        for key in seen:
            node = graph["nodes"].get(key, {})
            family = node.get("family")
            if family is not None and family not in EXCLUDED:
                seen_families.add(family)
            seen_conditions.update(
                re.findall(r"\b([A-Za-z_]\w*)\s*\(", node.get("criterion_raw") or "")
            )
            if node.get("kind") in ("state", "area") and "native_evidence_line" in node:
                dependencies[node["kind"]].add(node["reference"])
        seen_conditions.difference_update(
            {"not", "and", "or", "if", "then", "else", "True", "False"}
        )
        for family in seen_families:
            dependents[family].append(spell["spell_id"])
        for name in seen_conditions:
            conditions[name].append(spell["spell_id"])
    rows = [
        dict(
            family=family,
            status="partial_registered_route" if family in routes else "absent_route",
            registered=family in routes,
            dependent_spells=len(set(identities)),
            spell_ids=sorted(set(identities)),
            semantic_complete=None,
            manual_complete=None,
        )
        for family, identities in sorted(
            dependents.items(),
            key=lambda pair: (pair[0] in routes, -len(pair[1]), pair[0]),
        )
    ]
    present = sum(row["registered"] for row in rows)
    after = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in relative_paths
    }
    if after != digests:
        raise ValueError("Source changed during inventory capture; retry")
    result = dict(
        schema="non-summon-class-route-gaps-v2",
        scope="Class spells/extras and innates in the source-stable native typed graph; creation/control families excluded, creature ability books not expanded",
        excluded_families=sorted(EXCLUDED),
        sources=digests,
        sources_stable=True,
        graph_native_counts=graph["counts"],
        metric=dict(
            name="registered_effect_route_coverage",
            numerator=present,
            denominator=len(rows),
            percent=round(100 * present / len(rows), 1),
        ),
        semantic_completion_percent=None,
        families=rows,
        criteria=[
            dict(
                name=name,
                status="pending_contract_verification",
                spell_ids=sorted(set(identities)),
            )
            for name, identities in sorted(conditions.items())
        ],
        states=sorted(dependencies["state"]),
        areas=sorted(dependencies["area"]),
        limitations=[
            "A registered route can be partial, gated, incorrect or unreachable.",
            "Unregistered family dependencies are potential gaps, not proof every dependent spell fails.",
            "This classified graph does not certify dynamic reference, event, condition or class-mechanic completeness.",
            "State and area identities are enumerated; their lifecycle semantics remain unverified here.",
            "The metric is implementation registration coverage, never functional spell completion.",
        ],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
    with output.with_suffix(".csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row, spell_ids=json.dumps(row["spell_ids"])))
    lines = [
        "# Class effect route gaps excluding creature creation/control",
        "",
        f"Registered routes: **{present}/{len(rows)} ({result['metric']['percent']}%)**.",
        "This measures source registrations, not working spells or completed mechanics.",
        "",
        f"Class criteria enumerated: {len(conditions)}; states: {len(dependencies['state'])}; areas: {len(dependencies['area'])}.",
        "The CSV contains every included family, its status and all dependent spell IDs.",
        "",
        "## Families without a registered route",
        "",
        "| Family | Structural dependent spells |",
        "|---|---:|",
    ]
    lines += [
        f"| {row['family']} | {row['dependent_spells']} |"
        for row in rows
        if not row["registered"]
    ]
    lines += ["", "## Verification still required", ""]
    lines += ["- " + value for value in result["limitations"]]
    output.with_suffix(".md").write_text("\n".join(lines) + "\n")
    return result["metric"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "docs/reports/combat-inventory/non-summon-gap-inventory-20261007",
    )
    print(json.dumps(build(parser.parse_args().output)))
