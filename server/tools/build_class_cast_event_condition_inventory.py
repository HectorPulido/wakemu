"""Audit class-owned cast-event criterion routes without runtime catalog imports."""
import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/reports/combat-inventory"


def build():
    graph_path = OUT / "class-native-mechanic-graph-20261007.json"
    source_path = ROOT / "server/wakfu_server/combat/combat_conditions.py"
    graph = json.loads(graph_path.read_bytes())
    routes = defaultdict(set)
    for function in ast.walk(ast.parse(source_path.read_text())):
        if not isinstance(function, ast.FunctionDef):
            continue
        for branch in ast.walk(function):
            if not isinstance(branch, ast.If):
                continue
            for comparison in ast.walk(branch.test):
                if not (
                    isinstance(comparison, ast.Compare)
                    and isinstance(comparison.left, ast.Name)
                    and comparison.left.id == "name"
                ):
                    continue
                for operand in comparison.comparators:
                    values = (
                        operand.elts
                        if isinstance(operand, (ast.Tuple, ast.List))
                        else [operand]
                    )
                    for value in values:
                        if isinstance(value, ast.Constant) and isinstance(
                            value.value, str
                        ):
                            routes[value.value].add(function.name)
    edges = defaultdict(list)
    for edge in graph["edges"]:
        edges[edge["source"]].append(edge["target"])
    seeds = [
        key
        for key, node in graph["nodes"].items()
        if set(
            node.get("native_definition", {}).get("native_fields", {}).get("Qa.beD")
            or []
        )
        & {1024, 1025, 28}
    ]
    closure = set(seeds)
    pending = list(seeds)
    for key in pending:
        for target in edges[key]:
            if target not in closure:
                closure.add(target)
                pending.append(target)
    calls = defaultdict(list)
    criteria = []
    for key in sorted(closure):
        raw = graph["nodes"][key].get("criterion_raw")
        if not raw:
            continue
        criteria.append(dict(node=key, raw=raw))
        for name in set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", raw)) - {
            "if",
            "then",
            "else",
            "and",
            "or",
            "not",
        }:
            calls[name].append(key)
    result = dict(
        schema=1,
        scope="Existing 18-class graph, native Qa.beD activation masks 1024/1025/28 and typed descendants",
        sources={
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (graph_path, source_path)
        },
        counts=dict(
            seeds=len(seeds),
            closure_nodes=len(closure),
            criteria=len(criteria),
            function_names=len(calls),
        ),
        route_policy="Explicit name branches only; a present branch is not functional accreditation. Generic fallthrough may implement additional names.",
        functions=[
            dict(
                name=name,
                effect_nodes=refs,
                python_functions=sorted(routes[name]),
                status="explicit_route" if routes[name] else "no_explicit_route",
            )
            for name, refs in sorted(calls.items())
        ],
        criteria=criteria,
    )
    destination = OUT / "class-cast-event-condition-inventory-20261008.json"
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    build()
