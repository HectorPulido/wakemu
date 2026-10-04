import ast
import json
import unittest
from pathlib import Path
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_local_criteria import (
    parse_local_criterion,
    LocalCriterionSyntax,
)


class LocalCriteriaTests(unittest.TestCase):
    def test_native_alias_binding_before_reassignment_and_long_overflow(self):
        c = ConditionContext({})
        self.assertTrue(evaluate_condition("a = 1; b = a; a = 2; b == 1 and a == 2", c))
        self.assertTrue(
            evaluate_condition(
                "n = 9223372036854775807; (n + 1) == (-9223372036854775807 - 1)", c
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("a == 2", c)

    def test_nested_conditional_and_missing_context_only_in_selected_branch(self):
        c = ConditionContext({})
        self.assertTrue(
            evaluate_condition(
                "n = if (False) then (GetLevel()) else if (True) then (2) else (3); n == 2",
                c,
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("n = if (True) then (GetLevel()) else (2); n == 2", c)
        self.assertTrue(
            evaluate_condition("if (True) then (True) else (IsCarried())", c)
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("if (True) then (True) else (Unsupported())", c)

    def test_mixed_numeric_if_uses_native_double_promotion(self):
        # alF.bDl requires BOTH numeric branches integral, even if one is unused.
        self.assertTrue(
            evaluate_condition(
                "n = if (True) then (9223372036854775807) else (1.5); (n + 1) > 0",
                ConditionContext({}),
            )
        )

    def test_real_eniripsa6967_cost_all_four_decks_and_remaining_unknown(self):
        audit = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "docs/reports/combat-inventory/active-cast-audit.json"
            ).read_text()
        )

        def find(x):
            if isinstance(x, dict):
                if x.get("spell_id") == 6967 and x.get("reason", "").startswith(
                    "Unsupported native criterion: cost ="
                ):
                    return x["reason"].removeprefix("Unsupported native criterion: ")
                for value in x.values():
                    result = find(value)
                    if result:
                        return result
            if isinstance(x, list):
                for value in x:
                    result = find(value)
                    if result:
                        return result

        source = find(audit)
        self.assertIsNotNone(source)
        parse_local_criterion(
            source
        )  # Exact installed expression, including remaining predicate.
        assignment = source.split(";")[0] + "; "
        for ids, cost in (((), 2), ((6988,), 3), ((6994,), 0), ((6988, 6994), 1)):
            c = ConditionContext(
                {
                    "caster": ConditionActor(
                        deck_spell_ids=frozenset(ids),
                        excluded_deck_spell_ids=frozenset(),
                        is_player=True,
                    )
                }
            )
            self.assertTrue(evaluate_condition(assignment + f"cost == {cost}", c))
            with self.assertRaisesRegex(
                UnknownCondition, "GetSpecificEffectAreaCountInRange"
            ):
                evaluate_condition(source, c)

    def test_no_python_execution_or_forward_aliases(self):
        for text in (
            "x = y; y = 1; True",
            'x = __import__("os").system("echo nope"); x == 0',
            "(lambda: True)()",
            "[x for x in []]",
            "x = 1;",
        ):
            with self.assertRaises((UnknownCondition, LocalCriterionSyntax)):
                evaluate_condition(text, ConditionContext({}))
