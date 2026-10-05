import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class StateThresholdTests(unittest.TestCase):
    def setUp(self):
        self.context = ConditionContext(
            {
                "caster": ConditionActor(
                    state_levels=((390, 2), (390, 100), (9312, 0))
                ),
                "target": ConditionActor(state_levels=((390, 5),)),
            }
        )

    def test_first_matching_level_is_threshold_not_equality_or_maximum(self):
        self.assertTrue(evaluate_condition("HasStateFromLevel(390, 1)", self.context))
        self.assertTrue(evaluate_condition("HasStateFromLevel(390, 2)", self.context))
        self.assertFalse(evaluate_condition("HasStateFromLevel(390, 3)", self.context))
        self.assertTrue(
            evaluate_condition('HasStateFromLevel(390, 5, "TARGET")', self.context)
        )
        self.assertFalse(
            evaluate_condition('HasStateFromLevel(390, 6, "target")', self.context)
        )

    def test_default_zero_threshold_and_absent_state(self):
        self.assertTrue(evaluate_condition("HasStateFromLevel(9312)", self.context))
        self.assertTrue(
            evaluate_condition('HasStateFromLevel(390, "target")', self.context)
        )
        self.assertFalse(evaluate_condition("HasStateFromLevel(999)", self.context))

    def test_missing_authority_and_invalid_signature_remain_errors(self):
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "HasStateFromLevel(390)", ConditionContext({"caster": ConditionActor()})
            )
        for expression in (
            "HasStateFromLevel()",
            'HasStateFromLevel(390, 2, "other")',
            "HasStateFromLevel(390, 2, 3)",
        ):
            with self.subTest(expression=expression), self.assertRaises(
                UnknownCondition
            ):
                evaluate_condition(expression, self.context)
