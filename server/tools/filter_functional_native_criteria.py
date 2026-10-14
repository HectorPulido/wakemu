"""Validate every reachable criterion branch without evaluating actor-dependent queries."""
import argparse
import hashlib
import json
from pathlib import Path
from build_monster_effect_work_queue import records
from wakfu_server.combat import combat_characteristic_conditions as characteristic
from wakfu_server.combat.combat_conditions import ConditionContext, evaluate_condition


def syntax_only_context():
    """Validate supported signatures without granting transaction authority."""

    def unavailable(*_args):
        raise ValueError("Syntax-only capability cannot evaluate runtime authority")

    return ConditionContext(
        actors={},
        random_number_query=unavailable,
        dungeon_difficulty_query=unavailable,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidates", "index", "lifecycle", "aliases", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--source", type=Path, action="append", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output must be new")
    pool = json.loads(args.candidates.read_text())
    index = json.loads(args.index.read_text())
    lifecycle = json.loads(args.lifecycle.read_text())
    aliases = json.loads(args.aliases.read_text())["aliases"]
    # Supply the exact sealed offline catalog data to the unchanged alias producer.
    characteristic.native_aliases = lambda: aliases
    effect_criteria = {}
    for path in args.source:
        for section, identity, row in records(
            path, {"effects", "baseline_effects", "spells", "states", "areas"}
        ):
            if section not in ("effects", "baseline_effects"):
                continue
            effect_criteria[identity] = row.get("criteria", "")
    initial = {}
    for row in lifecycle["rows"]:
        initial.setdefault(row["reference"], []).append(row)
    checked, failures = {}, {}

    def validate(raw):
        if not raw.strip():
            return True
        if raw not in checked:
            try:
                value = evaluate_condition(
                    "false and (" + raw + ")", syntax_only_context()
                )
                if value is not False:
                    raise ValueError("False wrapper did not short-circuit")
                checked[raw] = True
            except Exception as error:
                checked[raw] = False
                failures[raw] = type(error).__name__ + ": " + str(error)
        return checked[raw]

    accepted, rejected = [], []
    for candidate in pool["candidates"]:
        expressions = set()
        absent = []
        for ability in candidate["book"]:
            spell = index["spell_index"][str(ability["context"]["spell_id"])]
            expressions.add((spell.get("casting") or {}).get("criterion", ""))
            for effect in spell["effect_ids"]:
                identity = str(effect)
                if identity not in effect_criteria:
                    absent.append(["effect", identity])
                else:
                    expressions.add(effect_criteria[identity])
        for row in initial.get(candidate["reference"], []):
            if row.get("missing_source_node"):
                absent.append(row["missing_source_node"])
            expressions.add(row.get("criterion", ""))
        unsupported = [raw for raw in sorted(expressions) if not validate(raw)]
        if absent or unsupported:
            rejected.append(
                {
                    "reference": candidate["reference"],
                    "actor_level": candidate["actor_level"],
                    "missing_source_nodes": absent,
                    "unsupported_criteria": {
                        raw: failures.get(raw) for raw in unsupported
                    },
                }
            )
        else:
            candidate["all_reachable_native_criteria_support_checked"] = True
            candidate["nonempty_criteria_count"] = sum(
                bool(raw.strip()) for raw in expressions
            )
            candidate[
                "criteria_validation_method"
            ] = "Unchanged evaluate_condition(false AND native expression) validates all AST branches before short circuit; exact sealed characteristic aliases, empty actor mapping never queried."
            candidate["requires_reachable_effect_criteria_supported_review"] = False
            candidate["qualification_mode"] = "FUNCTIONAL_NATIVE_CONTEXT"
            accepted.append(candidate)
    pool.update(
        candidates=accepted,
        candidate_count=len(accepted),
        rejected_criteria_or_source_contexts=rejected,
        parent_contract_approved_mode="FUNCTIONAL_NATIVE_CONTEXT",
        unique_nonempty_criteria_checked=len(checked),
        unsupported_criteria=failures,
        actual_ai_damage_and_four_invariants_still_required=True,
        actual_ai_trace_unsupported_errors_must_reject=True,
        runtime_authority_producers_not_proven_by_false_wrapper=True,
        syntax_only_capabilities=["GetRandomNumber", "GetDungeonDifficulty"],
        input_sha256={
            str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [
                args.candidates,
                args.index,
                args.lifecycle,
                args.aliases,
                *args.source,
                Path(__file__),
            ]
        },
    )
    args.output.write_text(json.dumps(pool, separators=(",", ":")) + "\n")
    print(
        json.dumps(
            {
                "accepted": len(accepted),
                "rejected": len(rejected),
                "criteria_checked": len(checked),
                "unsupported": len(failures),
            }
        )
    )


if __name__ == "__main__":
    main()
