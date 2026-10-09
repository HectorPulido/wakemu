"""Inventory scoped native casting tables without importing the runtime catalogs."""
import gzip
import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/reports/combat-inventory"


def read(path):
    with gzip.open(path, "rt") if path.suffix == ".gz" else open(path, "rt") as stream:
        return json.load(stream)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lexical_calls(raw):
    """Read call-shaped identifiers outside quoted native string literals.

    This is a lexical inventory, not an inferred native predicate AST.
    Escaped quote characters and line/block comments are masked explicitly.
    """
    clean = list(raw)
    index = 0
    issues = []
    while index < len(raw):
        start = index
        char = raw[index]
        if char in ("'", '"'):
            quote = char
            index += 1
            closed = False
            while index < len(raw):
                if raw[index] == "\\":
                    index += 2
                elif raw[index] == quote:
                    index += 1
                    closed = True
                    break
                else:
                    index += 1
            if not closed:
                issues.append("unterminated_quoted_literal")
        elif raw.startswith("//", index):
            end = raw.find("\n", index)
            index = len(raw) if end < 0 else end
        elif raw.startswith("/*", index):
            end = raw.find("*/", index + 2)
            index = len(raw) if end < 0 else end + 2
            if end < 0:
                issues.append("unterminated_block_comment")
        else:
            index += 1
            continue
        clean[start : min(index, len(raw))] = " " * (min(index, len(raw)) - start)
    names = sorted(
        set(re.findall(r"([A-Za-z_][A-Za-z_0-9]*)\s*\(", "".join(clean)))
        - {"if", "then", "else", "not", "and", "or"}
    )
    return names, issues


def main():
    inputs = [
        ROOT / "server/protocol" / name
        for name in (
            "native-spell-casting.json",
            "native-class-spell-level-zero.json",
            "native-class-casting-roots.json",
        )
    ]
    inputs += [
        REPORT / "class-native-mechanic-components-20261007.json",
        REPORT / "class-condition-gap-inventory.json",
    ]
    inputs += sorted((ROOT / "server/wakfu_server/combat").glob("*casting*.py"))
    inputs += [ROOT / "server/wakfu_server/combat/combat_conditions.py", Path(__file__)]
    native_ast_path = REPORT / "class-casting-native-ast-20261007.jsonl.gz"
    native_ast_manifest = REPORT / "class-casting-native-ast-20261007.json"
    inputs += [native_ast_path, native_ast_manifest]
    before = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    catalog, zero, roots, components, conditions = map(read, inputs[:5])
    scope = zero["casting"]
    predicates = {c["name"]: c for c in conditions["conditions"]}
    direct_owners = defaultdict(list)
    owners = defaultdict(list)
    for row in components["classes"]:
        for spell in row["class_spell_ids"] + row["class_extra_ids"]:
            direct_owners[spell].append(row["breed"])
        for node in row["spell_dependency_components"].get("spell", []):
            owners[int(node.split(":", 1)[1])].append(row["breed"])
    for spell, classes in direct_owners.items():
        owners[spell] = sorted(set(owners[spell]) | set(classes))
    expressions, rows, missing = [], [], []
    calls = defaultdict(
        lambda: {"spell_ids": set(), "class_ids": set(), "locations": []}
    )
    for spell_id in sorted(scope, key=int):
        spell = int(spell_id)
        source = catalog["spells"].get(spell_id)
        if source is None:
            missing.append(spell)
            continue
        # Preserve every native field and all level samples; no inferred defaults.
        rows.append(
            {
                "spell_id": spell,
                "class_ids": owners[spell],
                "direct_seed_class_ids": direct_owners[spell],
                "transitive_dependency_class_ids": owners[spell],
                "native_casting": source,
                "level_zero": zero["spells"].get(spell_id),
                "status": "exported_partial_runtime_contract",
                "reachability": "unknown",
            }
        )
        candidates = [("cast_criterion_raw", source.get("cast_criterion_raw", ""))]
        candidates += [
            ("conditional:" + str(i), c.get("criteria", ""))
            for i, c in enumerate(source.get("conditional", []))
        ]
        for location, raw in candidates:
            if not raw:
                continue
            names, lexical_issues = lexical_calls(raw)
            expressions.append(
                {
                    "spell_id": spell,
                    "class_ids": owners[spell],
                    "direct_seed_class_ids": direct_owners[spell],
                    "transitive_dependency_class_ids": owners[spell],
                    "location": location,
                    "raw": raw,
                    "function_names": names,
                    "lexical_scan_issues": lexical_issues,
                    "native_ast": "not_exported_in_casting_table",
                    "status": "partial_requires_casting_context_contract",
                }
            )
            for name in names:
                calls[name]["spell_ids"].add(spell)
                calls[name]["class_ids"].update(owners[spell])
                calls[name]["locations"].append(
                    {"spell_id": spell, "location": location}
                )
    with gzip.open(native_ast_path, "rt") as stream:
        native_ast_rows = [json.loads(line) for line in stream]
    native_asts = {row["expression_id"]: row for row in native_ast_rows}
    if len(native_asts) != len(expressions) or len(native_ast_rows) != len(expressions):
        raise RuntimeError("Native casting AST denominator mismatch")
    for expression in expressions:
        key = f"spell:{expression['spell_id']}/{expression['location']}"
        authority = native_asts.get(key)
        raw_hash = hashlib.sha256(expression["raw"].encode("utf-8")).hexdigest()
        if (
            authority is None
            or authority["expression"] != expression["raw"]
            or authority["expression_sha256"] != raw_hash
        ):
            raise RuntimeError("Native casting AST identity mismatch: " + key)
        expression["expression_id"] = key
        expression["expression_sha256"] = raw_hash
        expression["native_ast"] = authority["native_parse"]
        expression["native_calls"] = authority["calls"]
        expression["local_parse"] = authority["local_parse"]
        expression["parse_comparison"] = authority["parse_comparison"]
    call_rows = []
    for name, refs in sorted(calls.items()):
        effect = predicates.get(name)
        call_rows.append(
            {
                "name": name,
                **{k: sorted(v) if isinstance(v, set) else v for k, v in refs.items()},
                "effect_inventory_status": effect.get("status")
                if effect
                else "casting_only_not_in_effect_inventory",
                "native_parser_class": effect.get("native_class") if effect else None,
                "python_routes": effect.get("python_routes", []) if effect else [],
                "provider_dependencies": effect.get("provider_dependencies", [])
                if effect
                else [],
                "casting_route_status": "partial_not_certified_by_effect_route",
                "native_ast_status": "original_casting_parser_exported",
            }
        )
    after = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    result = {
        "schema": "class-casting-gap-inventory-v1",
        "scope": "851 scoped class/extras/class-summon dependency spells; excludes general monsters",
        "sources_before": before,
        "sources_after": after,
        "sources_stable": before == after,
        "counts": {
            "scoped_spells": len(scope),
            "present_spells": len(rows),
            "missing_spells": len(missing),
            "expressions": len(expressions),
            "conditional_rows": sum(
                len(r["native_casting"].get("conditional", [])) for r in rows
            ),
            "casting_function_names": len(calls),
            "casting_only_function_names": sum(
                r["effect_inventory_status"] == "casting_only_not_in_effect_inventory"
                for r in call_rows
            ),
            "native_casting_roots": len(roots["roots"]),
            "native_ast_expressions": len(native_asts),
            "spells_with_structural_class_reverse_index": sum(
                bool(r["class_ids"]) for r in rows
            ),
            "spells_without_direct_seed_owner": sum(
                not r["direct_seed_class_ids"] for r in rows
            ),
            "expressions_with_lexical_issues": sum(
                bool(e["lexical_scan_issues"]) for e in expressions
            ),
        },
        "missing_spells": missing,
        "spells": rows,
        "expressions": expressions,
        "function_reverse_index": call_rows,
        "native_root_contracts": roots,
        "route": [
            "native conditional table",
            "evaluate_condition with casting context",
            "resolve range/costs",
            "native casting eligibility",
            "owned actor/provider/selector context",
        ],
        "limitations": [
            "Casting predicate occurrence is distinct from effect criterion occurrence.",
            "Effect evaluator registration is not a proven casting adapter contract.",
            "851 dependency spells includes the fixed scoped summon book, not dynamic captured species.",
            "Native ASTs are original production-parser trees; parse success does not evaluate providers or certify casting.",
            "Roots preserve native selectors/geometry; dependency presence does not prove executable reachability.",
        ],
        "class_reverse_index_policy": "Direct seeds and transitive spell dependency classes are explicit and separate; no innate closure used. Structural ancestry is not executable class usage.",
        "lexical_scan_policy": "Call-shaped identifiers outside escaped quoted literals and comments; native AST mapping remains unknown.",
        "functional_completion_percent": None,
    }
    if before != after:
        raise RuntimeError("Inputs changed during inventory build")
    output = REPORT / "class-casting-gap-inventory-20261007.json"
    with open(output, "wt") as stream:
        json.dump(result, stream, separators=(",", ":"))
    counts = result["counts"]
    text = "# Class casting criteria and root inventory — 2026-10-07\n\n"
    text += "This separate denominator preserves every native casting field, conditional expression, sampled level range/cost, and root selector/geometry. It does not infer casting support from the effect-criterion inventory.\n\n"
    text += "| Dimension | Count |\n| --- | ---: |\n" + "".join(
        f"| {k} | {v} |\n" for k, v in counts.items()
    )
    text += "\n[Complete machine inventory](class-casting-gap-inventory-20261007.json) contains per-spell class reverse indices, raw expressions, function names, source routes/providers where separately inventoried, and all native root contracts. Original native casting ASTs are attached for all968 expressions after exact raw-hash identity checks; no parsed AST certifies its runtime provider.\n\nAll source hashes were stable during generation. Complete functional and client acceptance remain unknown.\n"
    (REPORT / "class-casting-gap-inventory-20261007.md").write_text(text)
    print(json.dumps({"counts": counts, "sources_stable": before == after}))


if __name__ == "__main__":
    main()
