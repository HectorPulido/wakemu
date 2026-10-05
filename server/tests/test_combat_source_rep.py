import unittest
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.combat_trigger_identifiers import condition_identifiers


class NativeSourceREPTests(unittest.TestCase):
    def context(self, source):
        return ConditionContext({}, **condition_identifiers(source))

    def test_actual_source_flags_and_long_to_int(self):
        c = self.context({"effect_flags": (4, 28)})
        self.assertTrue(evaluate_condition("IsTriggeredByEffectWithREP(28)", c))
        self.assertFalse(evaluate_condition("IsTriggeredByEffectWithREP(15)", c))
        self.assertTrue(evaluate_condition("IsTriggeredByEffectWithREP(4294967324)", c))

    def test_absent_source_false_but_present_unknown_rejects(self):
        self.assertFalse(
            evaluate_condition("IsTriggeredByEffectWithREP(28)", self.context(None))
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsTriggeredByEffectWithREP(28)", self.context({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "IsTriggeredByEffectWithREP(7)", self.context({"effect_flags": ()})
            )

    def test_numeric_boolean_selector_rejects(self):
        for expr in ("GetTeamId(1) == 0", "GetTeamId(True) == 0"):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expr, ConditionContext({}))
