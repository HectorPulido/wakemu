"""Compile bounded source-qualified transition recipes without loading runtime catalogs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from audit_class_conditional_transitions import transition_cases, annotate_source_paths


def build(plan_path):
    plan_path = Path(plan_path)
    matrix_path = plan_path.parent / "class-casting-precondition-matrix-20261008.json"
    graph_path = plan_path.parent / "class-native-mechanic-graph-20261007.json"
    plans = json.loads(plan_path.read_text())["plans"]
    matrix = json.loads(matrix_path.read_text())
    parameters = {
        row["effect"]: row["raw_parameters"]
        for index in matrix["state_source_index"].values()
        for row in index["native_state_apply_candidates"]
    }
    for plan in plans:
        for preparation in plan["preparation"]:
            for caller in preparation["caller_candidates"]:
                caller["native_state_parameters"] = parameters.get(
                    caller["native_state_applicator"]
                )
    cases, inventory = transition_cases(plans, (20, 200), 96)
    annotate_source_paths(cases, graph_path)
    signatures = Counter()
    recipes = []
    for case in cases:
        domains = ["actual_ready", "actual_owned_turn", "native_conditional_selection"]
        if case["caller_is_passive"]:
            domains.append("ready_passive_prerequisite")
        if case["ancestor_counter_requirements"]:
            domains.append("real_turn_counter_preparation")
        if case["setup_producers"]:
            domains.append("qualified_source_prerequisite_actions")
        if any(row.get("caller_is_passive") for row in case["setup_producers"]):
            domains.append("real_passive_turn_boundaries")
        if case["unavailable_deck_references"] or case["qualified_caller_rank"][0]:
            domains.append("actual_dynamic_book_required")
        signature = "|".join(sorted(domains))
        signatures[signature] += 1
        recipes.append(
            dict(
                case=case,
                shared_execution_signature=signature,
                gameplay_verified=False,
                branch_verified=False,
                removal_control_verified=False,
                execution_contract=[
                    "preserve_actual_ready_source",
                    "qualify_current_owned_book_and_complete_boolean_guards",
                    "prepare_and_commit_real_producer",
                    "observe_ordered_state_uid_and_exact_level",
                    "prepare_and_commit_requested_native_branch",
                    "independent_actual_consumption_or_expiry_control",
                    "prepare_and_commit_restored_native_selection",
                ],
            )
        )
    sources = [
        plan_path,
        matrix_path,
        graph_path,
        Path("server/tools/audit_class_conditional_transitions.py"),
    ]
    return dict(
        schema="class-conditional-execution-manifest-v1",
        levels=[20, 200],
        scope="Bounded state/level producer representatives; not all 651 native branches",
        inventory=inventory,
        execution_signature_counts=dict(signatures),
        source_hashes={
            str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources
        },
        runtime_catalog_loaded=False,
        runtime_executed=False,
        recipes=recipes,
        full_execution_command="PYTHONPATH=server:server/tools /tmp/wakemu-combat-review-venv/bin/python3 "
        "server/tools/audit_class_conditional_transitions.py "
        ".runtime/combat-review-20261008/class-conditional-transitions-all75-01.json "
        "--levels 20 200 --maximum-cases 96 --candidate-limit 256",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path(
            "docs/reports/combat-inventory/class-casting-transition-plan-20261008.json"
        ),
    )
    args = parser.parse_args()
    report = build(args.plan)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                inventory=report["inventory"],
                signatures=report["execution_signature_counts"],
            )
        )
    )
