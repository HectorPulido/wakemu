#!/usr/bin/env python3
"""Inventory conditional preparation dependencies without injecting native facts."""
import argparse
import ast
from collections import Counter, defaultdict, deque
import csv
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.combat_local_criteria import parse_local_criterion

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "docs/reports/combat-inventory"


def read(path):
    with open(path, "rt") as stream:
        return json.load(stream)


def literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return dict(expression=ast.dump(node, include_attributes=False))


def domain(name):
    if name in (
        "HasState",
        "GetStateLevel",
        "HasStateFromLevel",
        "GetStateCountInRange",
    ):
        return "state"
    if name in ("IsSpellInDeck", "GetSpellLevel"):
        return "owned_book_or_deck"
    if name == "HasFightProperty":
        return "fight_property"
    if name in ("GetCharac", "GetCharacteristic", "GetCharacMax", "GetLevel"):
        return "live_characteristic"
    if name in ("HasEffectWithSpecificId",):
        return "retained_effect"
    if name in (
        "IsOwnSummon",
        "IsSummonedFromSymbiot",
        "IsControlledByAI",
        "HasSummonWithBreed",
        "IsBreed",
    ):
        return "summon_controller_or_morph"
    if name in ("IsCarrying",):
        return "physical_carry"
    if name in (
        "GetEffectCaster",
        "GetEffectTarget",
        "GetPhysicalRadius",
        "GetDistanceBetweenCasterAndTarget",
    ):
        return "actor_or_cell_geometry"
    if name == "IsInFight":
        return "fight_context"
    if name == "GetItemQuantity":
        return "owned_inventory"
    return "unclassified_native_provider"


def main(output):
    paths = [
        ROOT / "server/protocol/native-spell-casting.json",
        REPORTS / "class-native-mechanic-components-20261007.json",
        REPORTS / "class-native-mechanic-graph-20261007.json",
        ROOT / "server/wakfu_server/combat/combat_local_criteria.py",
    ]
    before = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    }
    casting = read(paths[0])["spells"]
    components = read(paths[1])["classes"]
    graph = read(paths[2])
    ownership = defaultdict(set)
    innate_owners = defaultdict(set)
    innate_effect_owners = defaultdict(set)
    for row in components:
        for reference in row["class_spell_ids"] + row["class_extra_ids"]:
            ownership[reference].add(row["breed"])
        for key in row["innate_dependency_components"].get("effect", []):
            innate_effect_owners[key].add(row["breed"])
        for key in row["innate_seed_states"]:
            innate_owners[int(key.split(":")[1])].add(row["breed"])
    parent_cache = {}

    def producers(key):
        if key in parent_cache:
            return parent_cache[key]
        queue = deque([(key, 0)])
        seen = set()
        parents = []
        while queue:
            node, depth = queue.popleft()
            if node in seen:
                continue
            seen.add(node)
            if node.startswith("spell:") and int(node.split(":")[1]) in ownership:
                reference = int(node.split(":")[1])
                parents.append(
                    dict(
                        spell=reference,
                        breeds=sorted(ownership[reference]),
                        depth=depth,
                    )
                )
            queue.extend(
                (graph["edges"][i]["source"], depth + 1)
                for i in graph["reverse_index"].get(node, ())
            )
        parent_cache[key] = parents
        return parents

    state_cache = {}

    def state_sources(reference):
        if reference in state_cache:
            return state_cache[reference]
        candidate = []
        for i in graph["reverse_index"].get("state:" + str(reference), ()):
            edge = graph["edges"][i]
            node = graph["nodes"].get(edge["source"], {})
            if node.get("family") != 304:
                continue
            candidate.append(
                dict(
                    effect=node["reference"],
                    native_runner_class=node.get("native_runner_class"),
                    raw_parameters=node.get("raw_parameters"),
                    criterion_raw=node.get("criterion_raw"),
                    class_spell_ancestors=producers(edge["source"]),
                    innate_component_owner_breeds=sorted(
                        innate_effect_owners[edge["source"]]
                    ),
                    innate_trigger_policy="Production Ready registers owning innate ancestry; actual source event/guard still required to apply this descendant state",
                    authority="native state-reference edge; guard/level/target reachability not proved",
                )
            )
        state_cache[reference] = dict(
            innate_owner_breeds=sorted(innate_owners[reference]),
            native_state_apply_candidates=candidate,
        )
        return state_cache[reference]

    policies = {
        "state": "Use production Ready for actual innate seeds, or actual owned spell/grant/retained trigger; verify committed target ledger and threshold. Never install the required state directly.",
        "owned_book_or_deck": "Use legal validated class deck and actual granted/captured/copied owned book. Deck membership and owned spell level are independent.",
        "fight_property": "Read complete actual native PB snapshot after legitimate creator/effect. Absence requires a complete snapshot; do not treat missing data as false.",
        "live_characteristic": "Use live native actor snapshot and actual resource/equipment/stat setters. Preserve costs and native turn refresh; no value override.",
        "retained_effect": "Use actual retained source and native effect identity; confirm UID/manager/ownership after execution.",
        "summon_controller_or_morph": "Use actual fresh/captured/copied descriptor, registration and native controller relation; ancestry is not a control grant.",
        "physical_carry": "Use production carrying interaction and registered reciprocal physical relationship; explicit null target is distinct from unknown actor.",
        "actor_or_cell_geometry": "Use native selected terrain, actual PV/cell target, live positions and controller authority. Null tooltip target cannot substitute for actual cast target.",
        "fight_context": "Use actual Ready/active fight and native invocation context.",
        "owned_inventory": "Use real owned inventory and supported acquisition/equipment producer; do not inject a predicate result.",
        "unclassified_native_provider": "Missing typed preparation policy; keep explicitly unknown.",
    }
    rows = []
    counts = Counter()
    function_counts = Counter()
    parse_failures = []
    for reference in sorted(ownership):
        record = casting.get(str(reference))
        if record is None:
            continue
        for index, rule in enumerate(record["conditional"]):
            raw = rule["criteria"]
            calls = []
            try:
                tree = parse_local_criterion(raw)
                parents = {
                    child: parent
                    for parent in ast.walk(tree)
                    for child in ast.iter_child_nodes(parent)
                }
                for call in ast.walk(tree):
                    if not isinstance(call, ast.Call):
                        continue
                    name = call.func.id
                    args = [literal(arg) for arg in call.args]
                    family = domain(name)
                    item = dict(
                        function=name,
                        arguments=args,
                        family=family,
                        preparation_policy=policies[family],
                        predicate_polarity="See exact AST/raw boolean expression; call occurrence alone does not assert positive requirement",
                    )
                    ancestor = parents.get(call)
                    negations = 0
                    tests = []
                    while ancestor is not None:
                        if isinstance(ancestor, ast.UnaryOp) and isinstance(
                            ancestor.op, ast.Not
                        ):
                            negations += 1
                        if isinstance(ancestor, ast.Compare):
                            tests.append(ast.unparse(ancestor))
                        ancestor = parents.get(ancestor)
                    item["enclosing_not_parity"] = negations % 2
                    item["enclosing_comparison_tests"] = tests
                    if family == "state" and args and type(args[0]) is int:
                        item["state_reference"] = args[0]
                        item["source_candidates"] = state_sources(args[0])
                        explicit_selector = next(
                            (arg for arg in args[1:] if isinstance(arg, str)), None
                        )
                        default_known = name in ("HasState", "GetStateLevel")
                        item["selector_contract"] = explicit_selector or (
                            "caster"
                            if default_known
                            else "native default selector: requires function contract"
                        )
                        item["selector_source"] = (
                            "explicit_literal"
                            if explicit_selector
                            else "native_eII.a_default"
                            if default_known
                            else "unresolved_native_default"
                        )
                    if family == "owned_book_or_deck" and args and type(args[0]) is int:
                        item["required_spell_reference"] = args[0]
                        item["source_candidates"] = producers("spell:" + str(args[0]))
                    calls.append(item)
                    counts[family] += 1
                    function_counts[name] += 1
                normalized_ast = ast.dump(tree, include_attributes=False)
            except Exception as error:
                normalized_ast = None
                parse_failures.append(
                    dict(spell=reference, branch=index, error=str(error))
                )
            changes = []
            for field in (
                "line_of_sight",
                "linear",
                "free_cell",
                "range_modifiable",
                "path_option",
                "diagonal",
                "linear_path",
                "allow_self",
            ):
                if record[field] != rule[field]:
                    changes.append(field)
            if record["costs"] != rule["levels"]:
                changes.append("costs")
            if [value[:2] for value in record["levels"]] != rule["ranges"]:
                changes.append("range")
            domains = sorted({call["family"] for call in calls})
            rows.append(
                dict(
                    spell=reference,
                    breeds=sorted(ownership[reference]),
                    branch=index,
                    criterion_raw=raw,
                    criterion_local_ast=normalized_ast,
                    changes=changes,
                    preparation_domains=domains,
                    calls=calls,
                    baseline_range_first_level=record["levels"][0][:2],
                    conditional_range_first_level=rule["ranges"][0],
                    baseline_cost_first_level=record["costs"][0],
                    conditional_cost_first_level=rule["levels"][0],
                    no_context_policy="Evaluate against complete actual Ready/owned actor and actual target. Missing authority is unknown; a false branch is a legitimate guarded scenario, not a failed mechanic.",
                    preparation_reachability="unknown until actual legal producer sequence is executed",
                    critical_policy="Casting table selection is independent of critical effect-root selection; critical producer is not inferred from a criterion name.",
                )
            )
    after = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    }
    report = dict(
        scope="All18 class conditional casting references; production preparation candidates, not reachable-state certification",
        class_count=len(components),
        conditional_reference_count=len({r["spell"] for r in rows}),
        branch_count=len(rows),
        family_occurrences=dict(counts),
        function_occurrences=dict(function_counts),
        production_preparation_policies=policies,
        state_source_index=state_cache,
        parse_failures=parse_failures,
        rows=rows,
        sources=before,
        sources_stable=before == after,
        limitations=[
            "Graph source edges can be guarded, level-dependent or transitive; they are candidate callers, not completed legal sequences.",
            "Casting branches are native exported positive-level tables. Level0 uses the separately exported same predicate contract and needs its own execution-level scenario.",
            "Transform/captured/copied books and target states require actual registered producers, not a synthetic condition dictionary.",
            "No generic crit/PB/morph requirement is added where the original criterion has none.",
        ],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    with output.with_suffix(".csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "spell",
                "breeds",
                "branch",
                "criterion_raw",
                "changes",
                "preparation_domains",
                "preparation_reachability",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(row[key])
                    if isinstance(row[key], list)
                    else row[key]
                    for key in writer.fieldnames
                }
            )
    print(
        json.dumps(
            dict(
                references=report["conditional_reference_count"],
                branches=len(rows),
                families=counts,
                parse_failures=len(parse_failures),
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
