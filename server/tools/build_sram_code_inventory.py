#!/usr/bin/env python3
"""Offline Sram dependency inventory; file artifacts never activate catalogs."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/reports/combat-inventory"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def criteria_names(criteria):
    return sorted(set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", "\n".join(criteria))))


def build(source, condition_rows, root=ROOT):
    nodes = source["nodes"]
    conditions = {r["name"]: r for r in condition_rows}
    effects = {k: v for k, v in nodes.items() if k.startswith("effect:")}
    families = Counter(r["family"] for r in effects.values())
    trap_edges = []
    for key, row in effects.items():
        if row.get("family") == 308 and row.get("native_runner_class") == "eYW":
            raw = row.get("raw_parameters", [])
            if len(raw) >= 2:
                reference = int(raw[0])
                trap_edges.append(
                    dict(
                        source=key,
                        target=f"area:{reference}",
                        kind="native_eYW_eYQ_parameter0_area",
                        growth=raw[1],
                        definition_in_graph=f"area:{reference}" in nodes,
                        source_proof="eYW extends eYQ; inherited configured prototype slot0",
                    )
                )
    spells = []
    for row in source["owned_spells"]:
        refs = row["effect_refs"]
        native = [effects[f"effect:{r}"] for r in refs if f"effect:{r}" in effects]
        names = criteria_names(row.get("criteria", []))
        spells.append(
            dict(
                reference=row["id"],
                name=row["name"],
                kind=row["kind"],
                unlock_level=row["unlock_level"],
                roots=row["root_effects"],
                effect_references=refs,
                state_references=row["states"],
                families=row["families"],
                criteria=row.get("criteria", []),
                conditions=[
                    dict(
                        name=n,
                        dated_status=conditions.get(n, {}).get("status", "unknown"),
                        accreditation="not inferred from branch presence",
                    )
                    for n in names
                ],
                gated_effects=[
                    r["reference"]
                    for r in native
                    if r.get("runtime_route", {}).get("status") == "gated"
                ],
                missing_definitions=row.get("missing_definitions", []),
                behavior_status="not comprehensively verified",
            )
        )
    guards = []
    bindings = {
        b["source"]
        for row in effects.values()
        for b in row.get("runtime_route", {}).get("bindings", [])
    }
    # Current source guard sites are evidence of explicit authority boundaries;
    # their presence does not mean every Sram invocation reaches that boundary.
    for name in sorted(bindings):
        path = root / name
        if not path.exists():
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and node.exc:
                guards.append(
                    dict(file=name, line=node.lineno, expression=ast.unparse(node.exc))
                )
    return dict(
        schema="sram-source-inventory-v1",
        breed=4,
        authority="PostgreSQL runtime catalog; these dated hash-pinned artifacts are offline evidence only",
        published_revision_at_source_export=source["published_catalog_revision"],
        counts=dict(
            active=sum(s["kind"] == "active" for s in spells),
            passives=sum(s["kind"] == "passive" for s in spells),
            grants=len(source["extra_spells"]),
            effects=len(effects),
            states=sum(k.startswith("state:") for k in nodes),
            areas=sum(k.startswith("area:") for k in nodes),
            profiles=sum(k.startswith("profile:") for k in nodes),
        ),
        spells=spells,
        granted_actions=source["extra_spells"],
        innate_states=source["innate_seed_states"],
        families=[dict(family=f, effects=n) for f, n in sorted(families.items())],
        effects=effects,
        typed_edges=source["typed_edges"],
        recovered_trap_dependency_edges=trap_edges,
        missing_trap_definition_references=sorted(
            {
                int(e["target"].split(":")[1])
                for e in trap_edges
                if not e["definition_in_graph"]
            }
        ),
        current_binding_guard_sites=guards,
        dated_mechanic_requirements=source["mechanic_requirement_units"],
        risks=[
            "Registered or gated handlers do not certify complete class behavior.",
            "Configuration gates are not missing handlers.",
            "Literal False native criteria are intentional disabled branches, not bypass candidates.",
            "Historical Double/trap reports do not certify invisibility, poison, hemorrhage or every passive.",
            "No live release pin comparison, catalog activation, restart or deployment was performed.",
        ],
    )


def main():
    input_path = BASE / "remaining-classes-20261010/4-inventory.json"
    conditions_path = BASE / "class-condition-gap-inventory.json"
    report = build(
        json.loads(input_path.read_text()),
        json.loads(conditions_path.read_text())["conditions"],
    )
    report["source_hashes"] = {
        str(p.relative_to(ROOT)): digest(p) for p in [input_path, conditions_path]
    }
    report["current_source_hashes"] = {
        name: digest(ROOT / name)
        for name in sorted({r["file"] for r in report["current_binding_guard_sites"]})
    }
    out = BASE / "sram-code-inventory-20261010.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Sram source inventory (2026-10-10)",
        "",
        "The dated graph denominator is superseded by sram-postgresql-closure-20261010.json.",
        "See sram-implementation-risk-manual-20261010.md for current counts and verification scope.",
        "This table retains the owned class book; it is not a gameplay completion claim.",
        "Runtime catalog authority remains PostgreSQL; no file fallback or activation is introduced.",
        "",
        str(report["counts"]),
        "",
        "| ID | Native name | Kind | Dependency effects | States | Gated effects |",
        "|---|---|---|---:|---|---:|",
    ]
    for r in report["spells"]:
        lines.append(
            f"| {r['reference']} | {r['name']} | {r['kind']} | {len(r['effect_references'])} | {', '.join(map(str,r['state_references']))} | {len(r['gated_effects'])} |"
        )
    lines += [
        "",
        "## Recovered dependency gap",
        "",
        "Native family308 /eYW inherits eYQ prototype slot0. The dated graph omitted",
        "these trap-area edges and their definition/child closure:",
        ", ".join(map(str, report["missing_trap_definition_references"])),
        "These omissions are inventory gaps, not automatically absent runtime definitions.",
    ]
    lines += ["", "## Risks and remaining verification", ""] + [
        "- " + r for r in report["risks"]
    ]
    lines += [
        "",
        "Every effect reference, raw criterion, family, route binding, typed reference edge,",
        "and requirement unit is retained in the companion JSON. Guard sites are current",
        "source observations and must be qualified by a real invocation before changing them.",
    ]
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print(json.dumps(report["counts"]))


if __name__ == "__main__":
    main()
