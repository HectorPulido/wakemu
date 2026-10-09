"""Inventory class native dependencies against actual production catalog wiring.

This is a code/data audit, not a combat scenario or a functionality percentage.
Run after rebuilding build_class_effect_route_inventory.py.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/reports/combat-inventory"


def read(path):
    opener = open
    with opener(path, "rt", encoding="utf8") as source:
        return json.load(source)


def build(breed=9):
    from wakfu_server.combat_server_spell import compiled_runtime_catalog
    from wakfu_server.spell_audit import states_catalog
    from wakfu_server.combat_native_spell_casting import catalog as casting_catalog
    from wakfu_server.combat_casting_context import casting_root_catalog

    graph = read(OUT / "class-native-mechanic-graph-20261007.json")
    components = read(OUT / "class-native-mechanic-components-20261007.json")
    class_scope = next(
        (row for row in components["classes"] if row["breed"] == breed), None
    )
    if class_scope is None:
        raise ValueError("Unknown native playable class identity")
    routes = read(OUT / "class-effect-route-inventory-20261008.json")
    route_map = {row["family"]: row for row in routes["families"]}
    effects = compiled_runtime_catalog().effects
    states = states_catalog()["states"]
    casting = casting_catalog()
    roots = casting_root_catalog()
    adjacency = defaultdict(set)
    for edge in graph["edges"]:
        if edge["target"] in graph["nodes"]:
            adjacency[edge["source"]].add(edge["target"])

    def closure(seed):
        seen = {seed}
        pending = [seed]
        while pending:
            for child in adjacency[pending.pop()]:
                if child not in seen:
                    seen.add(child)
                    pending.append(child)
        return seen

    with (OUT / "manual-acceptance-spell-register-20261007.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        register = {int(row["spell_id"]): row for row in csv.DictReader(source)}
    rows = []
    all_nodes = set()
    seeds = [
        ("spell", ref)
        for ref in class_scope["class_spell_ids"] + class_scope["class_extra_ids"]
    ]
    seeds += [
        ("state", int(key.split(":")[1])) for key in class_scope["innate_seed_states"]
    ]
    for kind, reference in seeds:
        nodes = closure(f"{kind}:{reference}")
        all_nodes.update(nodes)
        families = sorted(
            {
                graph["nodes"][node]["family"]
                for node in nodes
                if graph["nodes"][node].get("kind") == "effect"
                and graph["nodes"][node].get("family") is not None
            }
        )
        effect_ids = sorted(
            int(key.split(":")[1]) for key in nodes if key.startswith("effect:")
        )
        state_ids = sorted(
            int(key.split(":")[1]) for key in nodes if key.startswith("state:")
        )
        row = dict(
            reference=reference,
            domain=kind,
            name=class_scope["spell_labels"].get(
                str(reference), f"Innate state {reference}"
            ),
            kind=register.get(reference, {}).get("kind", "innate"),
            dependency_counts=dict(Counter(key.split(":")[0] for key in nodes)),
            dependencies=sorted(nodes),
            effect_families=families,
            missing_effect_definitions=[
                ref for ref in effect_ids if str(ref) not in effects
            ],
            missing_state_definitions=[
                ref for ref in state_ids if str(ref) not in states
            ],
            missing_handler_families=[
                family
                for family in families
                if not route_map.get(family, {}).get("bindings")
            ],
            gated_handler_families=[
                family
                for family in families
                if route_map.get(family, {}).get("status") == "gated"
            ],
        )
        if kind == "spell":
            row["casting_definition_present"] = str(reference) in casting
            native_roots = sorted(
                int(child.split(":")[1])
                for child in adjacency[f"spell:{reference}"]
                if child.startswith("effect:")
            )
            row["missing_native_casting_root_metadata"] = [
                ref for ref in native_roots if str(ref) not in roots["roots"]
            ]
        rows.append(row)
    sources = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "server/wakfu_server/combat").glob("*.py"))
    }
    result = dict(
        schema="class-code-dependency-audit-v1",
        breed=breed,
        scope="All owned and granted class spells and all native innate roots",
        roots=rows,
        total_dependency_counts=dict(Counter(key.split(":")[0] for key in all_nodes)),
        source_hashes=sources,
        limitations=[
            "Catalog presence and handler registration do not prove complete semantics.",
            "Gated bindings must be checked against the production factory and providers.",
            "Historical native closure is the dependency source; code is current.",
            "No missing implementation is inferred from a missing test.",
        ],
    )
    label = "cra" if breed == 9 else "class-" + str(breed)
    target = OUT / (label + "-code-dependency-inventory-20261008.json")
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                roots=len(rows),
                dependencies=result["total_dependency_counts"],
                missing_effects=sorted(
                    {ref for row in rows for ref in row["missing_effect_definitions"]}
                ),
                missing_states=sorted(
                    {ref for row in rows for ref in row["missing_state_definitions"]}
                ),
                missing_handlers=sorted(
                    {ref for row in rows for ref in row["missing_handler_families"]}
                ),
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--breed", type=int, default=9, help="Native breed identity; default Cra9"
    )
    build(parser.parse_args().breed)
