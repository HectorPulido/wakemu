#!/usr/bin/env python3
"""Plan guarded ordinary casting transitions; never materialize synthetic states."""
import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.combat_local_criteria import parse_local_criterion

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "docs/reports/combat-inventory"


def positive_states(raw):
    tree = parse_local_criterion(raw)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    states = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or node.func.id not in (
            "HasState",
            "HasStateFromLevel",
        ):
            continue
        if (
            not node.args
            or not isinstance(node.args[0], ast.Constant)
            or type(node.args[0].value) is not int
        ):
            continue
        ancestor = parents.get(node)
        negations = 0
        while ancestor is not None:
            if isinstance(ancestor, ast.UnaryOp) and isinstance(ancestor.op, ast.Not):
                negations += 1
            ancestor = parents.get(ancestor)
        if negations % 2 == 0:
            states.add(node.args[0].value)
    return states


def positive_state_requirement(call):
    if call.get("state_reference") is None or call["enclosing_not_parity"]:
        return False
    if call["function"] in ("HasState", "HasStateFromLevel"):
        for test in call["enclosing_comparison_tests"]:
            try:
                expression = ast.parse(test, mode="eval").body
                if (
                    isinstance(expression, ast.Compare)
                    and len(expression.ops) == 1
                    and isinstance(expression.ops[0], ast.Eq)
                    and isinstance(expression.comparators[0], ast.Constant)
                    and expression.comparators[0].value is False
                ):
                    return False
            except SyntaxError:
                pass
        return True
    if call["function"] != "GetStateLevel":
        return False
    for test in call["enclosing_comparison_tests"]:
        try:
            expression = ast.parse(test, mode="eval").body
        except SyntaxError:
            continue
        if not isinstance(expression, ast.Compare) or len(expression.ops) != 1:
            continue
        left = expression.left
        right = expression.comparators[0]
        operator = expression.ops[0]
        if (
            not isinstance(left, ast.Call)
            or left.func.id != "GetStateLevel"
            or not isinstance(right, ast.Constant)
            or type(right.value) is not int
        ):
            continue
        if (isinstance(operator, (ast.GtE, ast.Eq)) and right.value > 0) or (
            isinstance(operator, ast.Gt) and right.value >= 0
        ):
            return True
    return False


def main(args):
    matrix = json.loads(args.matrix.read_text())
    baseline = json.loads(args.baseline.read_text())
    with open(
        REPORTS / "class-native-mechanic-components-20261007.json", "rt"
    ) as stream:
        components = json.load(stream)["classes"]
    direct = {row["breed"]: set(row["class_spell_ids"]) for row in components}
    extras = {row["breed"]: set(row["class_extra_ids"]) for row in components}
    observations = defaultdict(list)
    for row in baseline["rows"]:
        for action in row.get("runtime_access", {}).get("actions", []):
            observations[action["reference"]].append(
                dict(
                    breed=row["breed"],
                    level=row["level"],
                    origin=action["origin"],
                    status=action["status"],
                    attempts=[
                        dict(
                            target=attempt["target"],
                            status=attempt["status"],
                            costs=attempt.get("costs"),
                            commit=attempt.get("representative_commit"),
                        )
                        for attempt in action["attempts"]
                    ],
                )
            )
    transition_evidence = defaultdict(list)
    sequence_paths = args.sequence_evidence or [
        ROOT / ".runtime/combat-review-20261008/cra-precision-manual-sequence-02.json"
    ]
    evidence_inputs = []
    for evidence_path in sequence_paths:
        if not evidence_path.is_file():
            continue
        evidence = json.loads(evidence_path.read_text())
        stable = evidence.get("sources_stable", evidence.get("source_stable"))
        evidence_inputs.append(
            dict(
                path=str(evidence_path.relative_to(ROOT)),
                sha256=hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
                sources_stable=stable,
            )
        )
        if stable is not True:
            continue
        for scenario_index, sequence in enumerate(evidence.get("rows", [])):
            grouped_steps = [
                ("ordinary_sequence", sequence.get("steps", [])),
                ("legacy_sequential_wall_followup", sequence.get("wall_followup", [])),
            ]
            grouped_steps.extend(
                (branch["name"], branch["steps"])
                for branch in sequence.get("wall_followup_branches", [])
            )
            for scenario_branch, step in [
                (name, step) for name, steps in grouped_steps for step in steps
            ]:
                if step.get("status") != "committed":
                    continue
                before_pairs = {
                    (state["reference"], state["level"])
                    for state in step.get("before", {}).get("states", [])
                }
                for state in step.get("after", {}).get("states", []):
                    if (state["reference"], state["level"]) in before_pairs:
                        continue
                    spell = step["spell"]
                    source_breeds = [
                        row["breed"]
                        for row in components
                        if spell in row["class_spell_ids"] + row["class_extra_ids"]
                    ]
                    transition_evidence[state["reference"]].append(
                        dict(
                            source_spell=spell,
                            caster_level=sequence.get("caster_level"),
                            breeds=source_breeds,
                            resulting_state_level=state["level"],
                            actor_id=step["after"]["id"],
                            state_caster_id=state.get("caster_id"),
                            state_target_id=state.get("target_id"),
                            scenario_index=scenario_index,
                            scenario_prefix=sequence.get("prefix"),
                            scenario_branch=scenario_branch,
                            before_states=step.get("before", {}).get("states", []),
                            after_states=step.get("after", {}).get("states", []),
                            turn_boundary_persistence="Not inferred from immediate post-commit state",
                            evidence=str(evidence_path.relative_to(ROOT)),
                            scope="Actual newly present/changed committed state; full conditional branch remains separate",
                        )
                    )
    dependencies = defaultdict(set)
    for state, sources in matrix["state_source_index"].items():
        for source in sources["native_state_apply_candidates"]:
            try:
                dependencies[int(state)].update(
                    positive_states(source["criterion_raw"])
                )
            except Exception:
                pass

    def cycles(state):
        pending = [(state, [state])]
        seen = set()
        found = []
        while pending:
            node, path = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            for other in dependencies[node]:
                if other in path:
                    found.append(path[path.index(other) :] + [other])
                else:
                    pending.append((other, path + [other]))
        return found

    plans = []
    counts = Counter()
    for branch in matrix["rows"]:
        preparation = []
        for call in branch["calls"]:
            if not positive_state_requirement(call):
                continue
            reference = call["state_reference"]
            sources = call["source_candidates"]
            candidates = []
            for source in sources["native_state_apply_candidates"]:
                for parent in source["class_spell_ancestors"]:
                    common = sorted(set(parent["breeds"]) & set(branch["breeds"]))
                    if not common:
                        continue
                    permission = observations.get(parent["spell"], [])
                    candidates.append(
                        dict(
                            spell=parent["spell"],
                            breeds=common,
                            class_access="ordinary_class_deck"
                            if any(parent["spell"] in direct[breed] for breed in common)
                            else "native_extra_requires_actual_grant",
                            native_state_applicator=source["effect"],
                            native_guard=source["criterion_raw"],
                            guard_positive_state_dependencies=sorted(
                                positive_states(source["criterion_raw"])
                            )
                            if source["criterion_raw"]
                            else [],
                            source_depth=parent["depth"],
                            baseline_permission_observations=permission,
                            target_binding="Native state applicator targeting must be verified; caller ancestry does not bind caster/target state automatically",
                        )
                    )
            candidates.sort(
                key=lambda item: (
                    item["class_access"] != "ordinary_class_deck",
                    item["source_depth"],
                    item["spell"],
                )
            )
            trigger_sources = [
                dict(
                    source,
                    applicable_breeds=sorted(
                        set(branch["breeds"])
                        & set(source.get("innate_component_owner_breeds", []))
                    ),
                )
                for source in sources["native_state_apply_candidates"]
                if set(branch["breeds"])
                & set(source.get("innate_component_owner_breeds", []))
            ]
            innate = sorted(set(branch["breeds"]) & set(sources["innate_owner_breeds"]))
            status = (
                "actual_ready_seed_candidate"
                if innate and call.get("selector_contract") == "caster"
                else "actual_ready_retained_trigger_candidate"
                if trigger_sources
                else "ordinary_owned_caller_candidate"
                if any(c["class_access"] == "ordinary_class_deck" for c in candidates)
                else "guarded_grant_caller_candidate"
                if candidates
                else "missing_owned_producer_in_current_index"
            )
            preparation.append(
                dict(
                    state=reference,
                    selector=call.get("selector_contract"),
                    threshold_tests=call["enclosing_comparison_tests"],
                    status=status,
                    innate_owner_breeds=innate,
                    caller_candidates=candidates,
                    retained_innate_trigger_candidates=trigger_sources,
                    positive_guard_cycles=cycles(reference),
                    actual_transition_evidence=[
                        e
                        for e in transition_evidence[reference]
                        if set(e["breeds"]) & set(branch["breeds"])
                    ],
                    removal_control="Pending actual normal removal/expiry producer and committed absence evidence; no direct state deletion",
                )
            )
        stage = (
            "state_transition_candidates"
            if preparation
            else "nonstate_or_negative_guard_preparation"
        )
        counts[stage] += 1
        actual = observations.get(branch["spell"], [])
        prepared = sum(
            attempt["status"] == "prepared_transaction"
            for row in actual
            for attempt in row["attempts"]
        )
        committed = sum(
            bool(attempt["commit"] and attempt["commit"].get("status") == "committed")
            for row in actual
            for attempt in row["attempts"]
        )
        plans.append(
            dict(
                spell=branch["spell"],
                branch=branch["branch"],
                breeds=branch["breeds"],
                criterion_raw=branch["criterion_raw"],
                stage=stage,
                preparation=preparation,
                non_positive_or_dynamic_state_tests=[
                    call
                    for call in branch["calls"]
                    if call["family"] == "state"
                    and not positive_state_requirement(call)
                ],
                remaining_preparation_domains=[
                    domain
                    for domain in branch["preparation_domains"]
                    if domain != "state"
                ],
                normal_baseline=dict(
                    observed_spell_entries=len(actual),
                    prepared_targets=prepared,
                    committed_targets=committed,
                ),
                coverage={
                    field: "pending exact selected branch identity and committed before/after evidence"
                    for field in branch["changes"]
                },
                transition_steps=[
                    "production Ready and legal owned book",
                    "execute owned source actions under native guards",
                    "verify actual selector state ledger/threshold",
                    "execute original normal conditional request",
                    "execute original removal/expiry and verify restored request",
                ],
                classification="Candidate action graph, not a forced linear script or proof of reachability",
            )
        )
    result = dict(
        scope="All286 conditional references/651branches; candidate state transitions linked to normal baseline observations",
        counts=dict(counts),
        plans=plans,
        actual_transition_evidence_inputs=evidence_inputs,
        baseline=dict(
            path=str(args.baseline.relative_to(ROOT)),
            sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
            finished=baseline["finished"],
            source_stable=baseline["source_stable"],
            completed_decks=baseline["completed_cases"],
            expected_decks=baseline["expected_cases"],
            certification="Exact branch coverage not established by a prepared/committed spell alone",
        ),
        sources={
            str(args.matrix.relative_to(ROOT)): hashlib.sha256(
                args.matrix.read_bytes()
            ).hexdigest()
        },
        limitations=[
            "Positive guard cycles are candidate loops, not proof of unreachability; alternate real sources may break them.",
            "Granted extras require an actual owned UID and native grant lifecycle; reverse ancestry alone is insufficient.",
            "Threshold expressions and full boolean branches remain authoritative, including OR alternatives and negative guards.",
            "The normal baseline can be an in-progress report. Its source stability and completion are preserved verbatim.",
            "Evidence from different scenario variants cannot be combined into a simultaneous prepared state; validate the full criterion on one actual committed snapshot.",
            "Costs/range/LOS coverage remains pending when selected conditional branch identity was not recorded.",
        ],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                plans=len(plans), counts=counts, baseline_finished=baseline["finished"]
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix",
        type=Path,
        default=REPORTS / "class-casting-precondition-matrix-20261008.json",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT
        / ".runtime/combat-review-20261008/class-normal-casts-all18-01.json",
    )
    parser.add_argument("--sequence-evidence", type=Path, nargs="*")
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
