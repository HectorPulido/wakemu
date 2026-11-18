"""Read-only criterion readiness for published quest and reviewed dialogue scopes.

The evaluator registry, dispatch branches, query producers and NPC transforms are
read from their Python ASTs. No gameplay modules, database or catalog are loaded.
Visibility aHe and unrelated native dialogue nodes are deliberately excluded.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import runpy

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if raw.startswith(b"\x1f\x8b") else raw)


def function(tree, name):
    found = [
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
    ]
    if len(found) != 1:
        raise ValueError(f"Cannot qualify unique source function {name}")
    return found[0]


def compared_strings(tree, variable):
    """Get literal call-name branches, never arbitrary string/name occurrences."""
    result = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        if ast.dump(node.left) != ast.dump(variable):
            continue
        try:
            value = ast.literal_eval(node.comparators[0])
        except (ValueError, TypeError):
            continue
        if isinstance(node.ops[0], ast.Eq) and isinstance(value, str):
            result.add(value)
        elif isinstance(node.ops[0], ast.In) and isinstance(value, (tuple, list, set)):
            result.update(v for v in value if isinstance(v, str))
    return result


def source_support(root=ROOT):
    paths = {
        "shared": root / "server/wakfu_server/maps/dungeon_criteria.py",
        "npc": root / "server/wakfu_server/maps/quest_npc.py",
        "authority": root / "server/wakfu_server/maps/dungeon_achievement_authority.py",
        "parser": root / "server/wakfu_server/combat/combat_local_criteria.py",
        "effective_eligibility": root
        / "server/wakfu_server/achievements/native_effective_eligibility.py",
    }
    texts = {k: p.read_text() for k, p in paths.items()}
    trees = {k: ast.parse(v) for k, v in texts.items()}
    evaluator = function(trees["shared"], "evaluate")
    registry = None
    for node in ast.walk(evaluator):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "names" for t in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, set) or not all(isinstance(s, str) for s in value):
                raise ValueError(
                    "Shared predicate registry is not a literal string set"
                )
            registry = value
    if registry is None:
        raise ValueError("Cannot derive actual shared predicate registry")
    dispatch = compared_strings(
        function(evaluator, "visit"), ast.Name(id="name", ctx=ast.Load())
    )
    # Query adapters return literal predicate-keyed dicts of callable producers.
    authority = set()
    for node in ast.walk(function(trees["authority"], "queries_from_snapshot")):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            authority.update(
                k.value
                for k, v in zip(node.value.keys, node.value.values)
                if isinstance(k, ast.Constant)
                and isinstance(k.value, str)
                and isinstance(v, (ast.Lambda, ast.Name))
            )
    query_dispatch = set()
    for node in ast.walk(function(evaluator, "visit")):
        if isinstance(node, ast.If) and any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "queries"
            and n.func.attr == "get"
            for n in ast.walk(node)
        ):
            query_dispatch.update(
                compared_strings(node.test, ast.Name(id="name", ctx=ast.Load()))
            )
    transform = function(function(trees["npc"], "_criterion"), "visit_Call")
    npc_names = compared_strings(
        transform,
        ast.Attribute(
            value=ast.Attribute(
                value=ast.Name(id="node", ctx=ast.Load()), attr="func", ctx=ast.Load()
            ),
            attr="id",
            ctx=ast.Load(),
        ),
    )
    contextual = set()
    # A named transformation that reads an optional _criterion parameter cannot
    # be claimed globally available. Preserve the exact authority identifier.
    criterion = function(trees["npc"], "_criterion")
    optional = {
        arg.arg
        for arg, default in zip(criterion.args.kwonlyargs, criterion.args.kw_defaults)
        if isinstance(default, ast.Constant) and default.value is None
    }
    for node in ast.walk(transform):
        if isinstance(node, ast.If):
            names = compared_strings(
                node.test,
                ast.Attribute(
                    value=ast.Attribute(
                        value=ast.Name(id="node", ctx=ast.Load()),
                        attr="func",
                        ctx=ast.Load(),
                    ),
                    attr="id",
                    ctx=ast.Load(),
                ),
            )
            if names and any(
                isinstance(n, ast.Name) and n.id in optional for n in ast.walk(node)
            ):
                contextual.update(names)
    reset_callback = any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "_criterion"
        and any(
            k.arg == "reset_allowed"
            and isinstance(k.value, ast.Name)
            and k.value.id == "reset_allowed"
            for k in n.keywords
        )
        for n in ast.walk(function(trees["npc"], "available"))
    )
    parser = runpy.run_path(str(paths["parser"]))["parse_local_criterion"]
    return dict(
        registry=registry,
        dispatch=dispatch,
        authority=authority,
        query_dispatch=query_dispatch,
        npc=npc_names,
        contextual=contextual,
        reset_callback=reset_callback,
        parser=parser,
        effective_criterion=runpy.run_path(str(paths["effective_eligibility"]))[
            "criterion"
        ],
        hashes={k: hashlib.sha256(v.encode()).hexdigest() for k, v in texts.items()},
    )


def inspect_expression(expression, context, support, *, recurring_reset_ids=()):
    if not isinstance(expression, str):
        return dict(status="malformed", detail="criterion is not a string", calls=[])
    if not expression.strip():
        return dict(status="ready", calls=[])
    annotated = re.sub(
        r'@\("[^"\n]+"\)\s*([^@]+)@', lambda m: "(" + m[1] + ")", expression
    )
    annotated = re.sub(r"#([^#]+)#", lambda m: "(" + m[1] + ")", annotated)
    try:
        tree = support["parser"](annotated)
    except (ValueError, SyntaxError, TypeError) as exc:
        return dict(status="malformed", detail=str(exc), calls=[])
    calls, failures = [], []
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        if not isinstance(call.func, ast.Name):
            failures.append("nonlocal call syntax")
            continue
        name = call.func.id
        if context == "npc_dialogue" and name in support["npc"]:
            state = (
                "requires_context" if name in support["contextual"] else "npc_adapter"
            )
            if (
                state == "requires_context"
                and support.get("reset_callback") is True
                and name == "CanResetAchievement"
                and len(call.args) == 1
                and not call.keywords
                and isinstance(call.args[0], ast.Constant)
                and type(call.args[0].value) is int
                and call.args[0].value in recurring_reset_ids
            ):
                state = "qualified_recurring_context"
        elif name not in support["registry"]:
            state = "requires_adapter"
        elif name not in support["dispatch"]:
            state = "registry_without_dispatch"
        elif name in support["query_dispatch"] and name not in support["authority"]:
            state = "requires_query_authority"
        else:
            state = "shared"
        calls.append(
            dict(
                name=name,
                status=state,
                argument_count=len(call.args),
                has_keyword_arguments=bool(call.keywords),
            )
        )
        if state not in ("shared", "npc_adapter", "qualified_recurring_context"):
            failures.append(state)
    status = "requires_adapter" if failures else "ready"
    return dict(
        status=status,
        calls=calls,
        **({"detail": sorted(set(failures))} if failures else {}),
    )


def audit(native, publication, conversations, dialogues, support):
    from inspect_mission_archetypes import publication_index

    definitions = {r["d"]: r for r in native["definitions"]}
    scope = {quest for quest, objective in publication_index(publication)}
    for document in conversations:
        scope.update(r["d"] for r in document.get("definitions", ()))
    rows = []
    recurring_reset_ids = {
        r["quest_id"]
        for document in conversations
        for r in document.get("recurring_deliveries", ())
    }

    def add(expression, context, **where):
        rows.append(
            dict(
                where,
                context=context,
                expression=expression,
                **inspect_expression(
                    expression,
                    context,
                    support,
                    recurring_reset_ids=recurring_reset_ids,
                ),
            )
        )

    for identity in sorted(scope):
        definition = definitions.get(identity)
        if definition is None:
            rows.append(dict(quest_id=identity, status="missing_native_definition"))
            continue
        try:
            effective = support["effective_criterion"](definition)
        except (ValueError, KeyError) as exc:
            rows.append(
                dict(
                    quest_id=identity,
                    field="effective_cjI",
                    status="requires_native_adapter",
                    detail=str(exc),
                )
            )
        else:
            add(
                effective,
                "quest_earning",
                quest_id=identity,
                field="effective_cjI" if definition.get("cjW") else "cjI",
                native_raw_cjI=definition.get("cjI", ""),
            )
        for objective in definition.get("cjJ", ()):
            for field in ("ckc", "cke"):
                add(
                    objective.get(field, ""),
                    "objective_earning",
                    quest_id=identity,
                    objective_id=objective["d"],
                    field=field,
                )
    nodes = {r["id"]: r for r in dialogues["nodes"]}
    reviewed_nodes, reviewed_choices = set(), set()
    for document in conversations:
        for placement in document.get("placements", ()):
            for edge in placement.get("graph", ()):
                source, choice, target = edge
                reviewed_nodes.add(source)
                if target:
                    reviewed_nodes.add(target)
                reviewed_choices.add((source, choice))
    for node_id in sorted(reviewed_nodes):
        node = nodes.get(node_id)
        if node is None:
            rows.append(dict(node_id=node_id, status="missing_native_node"))
        else:
            add(
                node.get("criteria", ""),
                "npc_dialogue",
                node_id=node_id,
                field="node.criteria",
            )
    for node_id, choice_id in sorted(reviewed_choices):
        choice = next(
            (
                c
                for c in nodes.get(node_id, {}).get("choices", ())
                if c["id"] == choice_id
            ),
            None,
        )
        if choice is None:
            rows.append(
                dict(
                    node_id=node_id, choice_id=choice_id, status="missing_native_choice"
                )
            )
        else:
            add(
                choice.get("criteria", ""),
                "npc_dialogue",
                node_id=node_id,
                choice_id=choice_id,
                field="choice.criteria",
            )
    failures = [r for r in rows if r["status"] != "ready"]
    return dict(
        schema="wakemu.mission-predicate-readiness-v1",
        limitations=[
            "Static callee/dispatch/authority readiness is not runtime argument validation or gameplay acceptance.",
            "aHe visibility is excluded. Only reviewed graph nodes and choices are inspected.",
            "Context-dependent adapters remain explicit; no dummy truth values are executed.",
            "Draft findings should not reject unrelated installed bundles.",
        ],
        source_hashes=support["hashes"],
        support={k: sorted(v) for k, v in support.items() if isinstance(v, set)},
        summary=dict(
            scoped_definitions=len(scope),
            criteria=len(rows),
            nonempty_criteria=sum(bool(r.get("expression", "").strip()) for r in rows),
            findings=len(failures),
            status_counts=dict(Counter(r["status"] for r in rows)),
            unsupported_calls=dict(
                Counter(
                    c["name"]
                    for r in failures
                    for c in r.get("calls", ())
                    if c["status"]
                    not in ("shared", "npc_adapter", "qualified_recurring_context")
                )
            ),
        ),
        findings=failures,
        criteria=rows,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--publication", type=Path, required=True)
    parser.add_argument("--conversation", type=Path, action="append", default=[])
    parser.add_argument(
        "--dialogues",
        type=Path,
        default=ROOT / "database/protocol/npc-dialogues.json.gz",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        load(args.native),
        load(args.publication),
        [load(p) for p in args.conversation],
        load(args.dialogues),
        source_support(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
