"""Join scoped native state edges with spell and transitive innate ownership."""
import gzip
import ast
import hashlib
import json
from pathlib import Path

from wakfu_server.combat_local_criteria import parse_local_criterion

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "docs/reports/combat-inventory"
STATES = (3333, 3699, 6752, 6872, 7647, 7950, 9309, 9315)


def load(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def build(matrix, plan, components, states=STATES):
    rows = []
    for state in states:
        branches = [
            row
            for row in plan["plans"]
            if any(item["state"] == state for item in row["preparation"])
        ]
        breeds = sorted({breed for row in branches for breed in row["breeds"]})
        sources = []
        for source in matrix["state_source_index"][str(state)][
            "native_state_apply_candidates"
        ]:
            owners = sorted(
                row["breed"]
                for row in components["classes"]
                if "effect:" + str(source["effect"])
                in row["innate_dependency_components"].get("effect", [])
            )
            raw = source["criterion_raw"]
            functions = (
                sorted(
                    {
                        node.func.id
                        for node in ast.walk(parse_local_criterion(raw))
                        if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                    }
                )
                if raw
                else []
            )
            sources.append(
                dict(
                    source,
                    effect_class=304,
                    innate_component_owner_breeds=owners,
                    applicable_innate_component_owners=sorted(
                        set(owners) & set(breeds)
                    ),
                    guard_functions=functions,
                )
            )
        callers = sorted(
            {
                ancestor["spell"]
                for source in sources
                for ancestor in source["class_spell_ancestors"]
            }
        )
        innate_owners = sorted(
            {
                breed
                for source in sources
                for breed in source["applicable_innate_component_owners"]
            }
        )
        if callers:
            status = "extra_owned_book_fixture_omission_requires_actual_permission"
        elif innate_owners:
            status = "transitive_innate_producer_ownership_missing_from_current_planner"
        else:
            status = "no_state_apply_edge_in_current_scoped_graph"
        rows.append(
            dict(
                state=state,
                consuming_breeds=breeds,
                conditional_branch_count=len(branches),
                conditional_requests=[
                    dict(
                        spell=row["spell"],
                        branch=row["branch"],
                        criterion_raw=row["criterion_raw"],
                    )
                    for row in branches
                ],
                classification=status,
                state_apply_sources=sources,
                class_spell_ancestor_references=callers,
                transitive_innate_owner_breeds=innate_owners,
                actual_source_execution_verified=False,
                state_injection_allowed=False,
            )
        )
    return rows


if __name__ == "__main__":
    paths = [
        REPORTS / "class-casting-precondition-matrix-20261008.json",
        REPORTS / "class-casting-transition-plan-20261008.json",
        REPORTS / "class-native-mechanic-components-20261007.json",
    ]
    rows = build(*(load(path) for path in paths))
    output = dict(
        scope="Eight states omitted by bounded transition fixture qualification; not evidence of missing native implementations",
        rows=rows,
        sources={
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
        },
        extraction_strategy=[
            "Join native state-reference applicators with direct spell ancestry AND transitive class innate components.",
            "For retained innate producers, recover actual subscription/trigger path, whole ancestor guards, source spell aliases and typed target binding before replay.",
            "For actual extra books, use a legal Ready fixture including an empty active deck when appropriate; prove actual grants, never grant the caller manually.",
            "Seed original native lookup with every class casting AST state reference; absent graph edges do not establish a nonexistent native state.",
            "Resolve known native default selectors from their function contract; a report annotation is not a target alias.",
        ],
        native_execution_complete=False,
    )
    target = REPORTS / "class-conditional-state-producer-gaps-20261008.json"
    target.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            dict(
                states=len(rows),
                classifications={
                    kind: sum(row["classification"] == kind for row in rows)
                    for kind in sorted({row["classification"] for row in rows})
                },
            )
        )
    )
