import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class NativeIsPlayerTests(unittest.TestCase):
    def test_default_target_and_explicit_selectors(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(is_player=True),
                "target": ConditionActor(is_player=False),
            }
        )
        self.assertFalse(evaluate_condition("IsPlayer()", context))
        self.assertTrue(evaluate_condition('IsPlayer("CASTER")', context))
        self.assertFalse(evaluate_condition('IsPlayer("unknown")', context))
        self.assertTrue(
            evaluate_condition(
                'IsPlayer("triggeringCaster")',
                ConditionContext({"triggeringcaster": ConditionActor(is_player=True)}),
            )
        )

    def test_absent_target_is_false_but_unknown_authority_rejected(self):
        self.assertFalse(
            evaluate_condition(
                "IsPlayer()", ConditionContext({}, effect_target_absent=True)
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "IsPlayer()", ConditionContext({"target": ConditionActor()})
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsPlayer(1)", ConditionContext({}))
