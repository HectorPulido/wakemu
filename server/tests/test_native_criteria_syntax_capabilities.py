"""Syntax filtering must never draw RNG or pretend runtime authority exists."""
import unittest
from unittest.mock import patch
from tools.filter_functional_native_criteria import syntax_only_context
from wakfu_server.combat.combat_conditions import (
    evaluate_condition,
    ConditionContext,
    UnknownCondition,
)


@patch("wakfu_server.combat.combat_conditions.canonical_aliases", return_value={})
class SyntaxCapabilityTests(unittest.TestCase):
    def test_false_wrapper_accepts_native_random_without_draw(self, _aliases):
        self.assertFalse(
            evaluate_condition(
                "false and (GetRandomNumber(2) == 1)", syntax_only_context()
            )
        )

    def test_real_query_of_syntax_context_rejected(self, _aliases):
        for expression in ("GetRandomNumber(2) == 1", "GetDungeonDifficulty() == 1"):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, syntax_only_context())

    def test_runtime_missing_random_still_rejected(self, _aliases):
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetRandomNumber(2) == 1", ConditionContext({}))

    def test_bad_native_signature_still_rejected_inside_false(self, _aliases):
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "false and GetRandomNumber() == 1", syntax_only_context()
            )
