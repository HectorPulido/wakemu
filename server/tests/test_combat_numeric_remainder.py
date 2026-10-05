import unittest
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class NativeRemainderTests(unittest.TestCase):
    def test_signed_dividend_and_double_remainder(self):
        ctx = ConditionContext({})
        for expression in (
            "(5 % 2) == 1",
            "((-5) % 2) == -1",
            "(5 % (-2)) == 1",
            "((-5) % (-2)) == -1",
            "(5.5 % 2) == 1.5",
            "(5 % 2.5) == 0",
            "(if (True) then ((-5) % 2) else (0)) == -1",
        ):
            self.assertTrue(evaluate_condition(expression, ctx), expression)

    def test_authoritative_table_turn_and_unknown_or_nonfinite_policy(self):
        ctx = ConditionContext({}, fight_current_table_turn=3)
        self.assertTrue(evaluate_condition("GetFightCurrentTableTurn() % 2 == 1", ctx))
        ctx = ConditionContext({}, fight_current_table_turn=-3)
        self.assertTrue(evaluate_condition("GetFightCurrentTableTurn() % 2 == -1", ctx))
        for expression in ("GetFightCurrentTableTurn() % 2 == 1", "1 % 0 == 0"):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ConditionContext({}))
