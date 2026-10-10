"""Inventory exact static factory bindings; registration never proves execution."""
import ast
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.storage import native_catalog
from import_class_summon_dependencies import entries
from class_native_requirement_sources import (
    merged_nodes,
    verified_projection,
    referenced_projection_owners,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/reports/combat-inventory"
COMBAT = ROOT / "server/wakfu_server/combat"
SOURCES = {}


def read(path):
    data = native_catalog.read_bytes(path)
    SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    return data


def literal_constant(path, name):
    tree = ast.parse(read(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return list(ast.literal_eval(node.value))
    raise ValueError("Missing literal declaration " + name)


def build(output=None):
    read(Path(__file__).resolve())
    read(ROOT / "server/tools/class_native_requirement_sources.py")
    projection = BASE / "class-captured-native-typed-closure-20261008.jsonl.gz"
    manifest_path = BASE / "class-captured-native-typed-closure-20261008.json"
    runtime_path = ROOT / "server/protocol/native-class-captured-effect-closure.json"
    for path in (projection, manifest_path, runtime_path):
        read(path)
    captured_manifest, captured_references = verified_projection(
        projection, manifest_path, runtime_path
    )
    referenced = BASE / "class-triggered426-native-typed-closure-20261008.jsonl.gz"
    referenced_manifest_path = (
        BASE / "class-triggered426-native-typed-closure-20261008.json"
    )
    read(referenced)
    read(referenced_manifest_path)
    runtime = COMBAT / "combat_effect_runtime.py"
    tree = ast.parse(read(runtime))
    imported = {
        (n.module, a.name, a.asname or a.name)
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom)
        for a in n.names
    }
    required = {
        ("combat_damage_healing", "DAMAGE_FAMILIES", "DAMAGE_FAMILIES"),
        ("combat_damage_healing", "HEAL_ELEMENTS", "HEAL_ELEMENTS"),
        ("combat_displacement", "FAMILIES", "FAMILIES"),
        ("combat_set_current_characteristic", "FAMILIES", "SET_CURRENT_FAMILIES"),
    }
    if not required <= imported:
        raise ValueError("Changed imported family bindings")
    constants = {
        "DAMAGE_FAMILIES": literal_constant(
            COMBAT / "combat_damage_healing.py", "DAMAGE_FAMILIES"
        ),
        "HEAL_ELEMENTS": literal_constant(
            COMBAT / "combat_damage_healing.py", "HEAL_ELEMENTS"
        ),
        "FAMILIES": literal_constant(COMBAT / "combat_displacement.py", "FAMILIES"),
    }
    # Resolve only the actual imported set-current registry declaration.
    source = read(COMBAT / "combat_set_current_characteristic.py").decode()
    if (
        "native-set-current-characteristic.json" not in source
        or "FAMILIES = frozenset(map(int, set_current_registry()))" not in source
    ):
        raise ValueError("Set-current binding changed; inspect before resolving")
    constants["SET_CURRENT_FAMILIES"] = list(
        map(
            int,
            json.loads(
                read(ROOT / "server/protocol/native-set-current-characteristic.json")
            )["effects"],
        )
    )
    registry = json.loads(
        read(ROOT / "server/protocol/effect-characteristic-registry.json")
    )["effects"]
    routes = defaultdict(list)

    def resolve(expr):
        if isinstance(expr, ast.Name):
            if expr.id not in constants:
                raise ValueError("Unresolved binding " + expr.id)
            return constants[expr.id]
        return list(ast.literal_eval(expr))

    def add(ids, node, guards, source_path=runtime):
        for identity in ids:
            routes[int(identity)].append(
                dict(
                    source=str(source_path.relative_to(ROOT)),
                    line=node.lineno,
                    binding=ast.unparse(node),
                    construction_guards=guards,
                )
            )

    def walk(statements, guards=()):
        for node in statements:
            if isinstance(node, ast.If):
                walk(node.body, (*guards, ast.unparse(node.test)))
                walk(node.orelse, (*guards, "not (" + ast.unparse(node.test) + ")"))
            elif isinstance(node, ast.For):
                if (
                    ast.unparse(node.iter)
                    == "self.characteristic_registry['effects'].items()"
                ):
                    binding = next(
                        n
                        for n in node.body
                        if isinstance(n, ast.Assign)
                        and any(
                            ast.unparse(t) == "handlers[identity]" for t in n.targets
                        )
                    )
                    if any(
                        row["runner"] not in ("eWQ", "eWR", "eXE", "eYO")
                        for row in registry.values()
                    ):
                        raise ValueError("Unsupported characteristic runner")
                    add(map(int, registry), binding, guards)
                # Retention wrapping is not a registration.
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "handlers"
                    ):
                        add([ast.literal_eval(target.slice)], node, guards)
                    elif isinstance(target, ast.Name) and target.id == "handlers":
                        if not isinstance(node.value, ast.DictComp):
                            raise ValueError("Changed handler constructor")
                        add(resolve(node.value.generators[0].iter), node, guards)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if ast.unparse(call.func) == "handlers.update":
                    value = call.args[0]
                    ids = (
                        resolve(value.generators[0].iter)
                        if isinstance(value, ast.DictComp)
                        else ast.literal_eval(value).keys()
                        if all(isinstance(v, ast.Constant) for v in value.values)
                        else [ast.literal_eval(k) for k in value.keys]
                    )
                    add(ids, node, guards)

    factory = next(
        n
        for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "NativeEffectRuntimeFactory"
    )
    method = next(
        n
        for n in factory.body
        if isinstance(n, ast.FunctionDef) and n.name == "__call__"
    )
    walk(method.body)
    dispatcher = COMBAT / "combat_effect_dispatch.py"
    dtree = ast.parse(read(dispatcher))
    # The execution chain starts at 865; nested special-case checks are not routes.
    chains = [
        n
        for n in ast.walk(dtree)
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "effect['effect_class'] == 865"
    ]
    if len(chains) != 1:
        raise ValueError("Changed dispatcher execution chain")
    node = chains[0]
    while isinstance(node, ast.If):
        test = node.test
        if (
            not isinstance(test, ast.Compare)
            or ast.unparse(test.left) != "effect['effect_class']"
        ):
            raise ValueError("Unresolved dispatcher branch")
        value = ast.literal_eval(test.comparators[0])
        ids = [value] if isinstance(value, int) else value
        add(ids, node, (), dispatcher)
        node = (
            node.orelse[0]
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)
            else None
        )
    graph_path = BASE / "class-native-mechanic-graph-20261007.json"
    read(graph_path)
    components = json.loads(
        read(BASE / "class-native-mechanic-components-20261007.json")
    )
    owners = defaultdict(lambda: defaultdict(set))
    for cls in components["classes"]:
        for domain in ("spell_dependency_components", "innate_dependency_components"):
            for key in cls[domain].get("effect", []):
                owners[key][domain].add(cls["breed"])
    for reference in captured_references["effect"]:
        owners["effect:" + str(reference)]["captured_dependency_components"].add(2)
    source_membership = {
        key: {breed for values in scopes.values() for breed in values}
        for key, scopes in owners.items()
    }
    referenced_manifest, referenced_owners = referenced_projection_owners(
        referenced, referenced_manifest_path, source_membership
    )
    for key, breeds in referenced_owners.items():
        owners[key]["triggered_dependency_components"].update(breeds)
    families = defaultdict(list)
    for key, row in merged_nodes(graph_path, projection, referenced):
        if row.get("kind") == "effect" and row.get("family") is not None:
            families[row["family"]].append((key, row))
    rows = []
    for family, nodes in sorted(families.items()):
        bindings = routes.get(family, [])
        status = (
            "registered"
            if any(not b["construction_guards"] for b in bindings)
            else "gated"
            if bindings
            else "no_handler"
        )
        membership = {
            domain: sorted({breed for key, _ in nodes for breed in owners[key][domain]})
            for domain in (
                "spell_dependency_components",
                "innate_dependency_components",
                "captured_dependency_components",
                "triggered_dependency_components",
            )
        }
        rows.append(
            dict(
                family=family,
                status=status,
                bindings=bindings,
                effect_count=len(nodes),
                effect_nodes=[key for key, _ in nodes],
                affected_classes=membership,
                native_contracts=[
                    dict(
                        node=key,
                        **{
                            field: r.get(field)
                            for field in (
                                "native_evidence_line",
                                "raw_parameters",
                                "reference_semantics",
                                "subscription",
                                "owner_on_caster",
                                "reverse_subscription",
                                "global_subscription",
                                "event_target_code",
                                "event_caster_code",
                                "parameter_sample_levels",
                            )
                        },
                    )
                    for key, r in nodes
                ],
                native_runners=sorted(
                    {
                        r.get("native_runner_class")
                        or r.get("native_definition", {}).get("native_class", "unknown")
                        for _, r in nodes
                    }
                ),
                criteria=sorted(
                    {r["criterion_raw"] for _, r in nodes if r.get("criterion_raw")}
                ),
                functional_verified=None,
            )
        )
    after = {
        name: hashlib.sha256(native_catalog.read_bytes(ROOT / name)).hexdigest()
        for name in SOURCES
    }
    if after != SOURCES:
        raise ValueError("Source changed during inventory; retry")
    result = dict(
        schema="class-static-effect-routes-v1",
        sources=SOURCES,
        sources_stable=True,
        published_catalog_revision=native_catalog.release(),
        counts=dict(Counter(r["status"] for r in rows)),
        families=rows,
        native_breed_names={
            str(r["breed"]): r["native_class_name"] for r in components["classes"]
        },
        class_id_policy="Native aKe.d breed ID, never list position; dependency scope keys are layer names",
        captured_projection_counts=captured_manifest["counts"],
        referenced_projection_counts=referenced_manifest["counts"],
        scope="Exact typed18-class graph plus class2-owned capturable33 and nested8 native projection. Presence in innate closure is not proof of a failed spell.",
        limitations=[
            "Registration does not verify parameters, guards, retention, delivery or lifecycle.",
            "Gated denotes factory construction guards only; registered handlers can still require runtime authority.",
            "No functionality percentage is inferred.",
        ],
    )
    out = output or BASE / "class-effect-route-inventory-20261008"
    out.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
    gaps = sorted(
        (r for r in rows if r["status"] == "no_handler"),
        key=lambda r: (
            -len(set(sum(r["affected_classes"].values(), []))),
            -r["effect_count"],
            r["family"],
        ),
    )
    lines = [
        "# Current static class effect routes",
        "",
        "Rebuild: `python3 server/tools/build_class_effect_route_inventory.py`.",
        "",
        "Source-stable exact bindings: "
        + str(result["counts"])
        + ". These are route counts, not functional completion.",
        "",
        "Native IDs:2=OSAMODAS,9=CRA. All class columns list native breed IDs, not component positions.",
        "",
        "Exact captured projection41profiles/195spells/178states/21areas/2156effects is included. Class membership is structural; shared innates do not imply every spell fails.",
        "",
        "| Missing family | Effects | Direct class closure | Innate class closure | Captured class closure | Referenced class closure |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    lines += [
        f"| {r['family']} | {r['effect_count']} | {r['affected_classes']['spell_dependency_components']} | {r['affected_classes']['innate_dependency_components']} | {r['affected_classes']['captured_dependency_components']} | {r['affected_classes']['triggered_dependency_components']} |"
        for r in gaps
    ]
    lines += ["", "## Construction-gated bindings", ""]
    lines += [
        f"- Family {r['family']}: "
        + "; ".join(", ".join(b["construction_guards"]) for b in r["bindings"])
        for r in rows
        if r["status"] == "gated"
    ]
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            dict(counts=result["counts"], priorities=[r["family"] for r in gaps[:15]])
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    build(parser.parse_args().output)
