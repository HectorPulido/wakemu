import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class IsCarryingTests(unittest.TestCase):
    def test_default_caster_and_only_target_selector(self):
        ctx = ConditionContext(
            {
                "caster": ConditionActor(is_carrying=True),
                "target": ConditionActor(is_carrying=False),
            }
        )
        self.assertTrue(evaluate_condition("IsCarrying()", ctx))
        self.assertTrue(evaluate_condition('IsCarrying("other")', ctx))
        self.assertFalse(evaluate_condition('IsCarrying("TaRgEt")', ctx))

    def test_carried_does_not_imply_carrying_and_missing_authority_rejects(self):
        ctx = ConditionContext(
            {"caster": ConditionActor(is_carried=True, is_carrying=False)}
        )
        self.assertFalse(evaluate_condition("IsCarrying()", ctx))
        self.assertTrue(evaluate_condition("IsCarried()", ctx))
        for actors in ({}, {"caster": ConditionActor(is_carried=True)}):
            with self.assertRaises(UnknownCondition):
                evaluate_condition("IsCarrying()", ConditionContext(actors))

    def test_rebound_target_and_invalid_arguments(self):
        ctx = ConditionContext({"target": ConditionActor(is_carrying=True)})
        self.assertTrue(evaluate_condition('IsCarrying("target")', ctx))
        for text in ("IsCarrying(1)", 'IsCarrying("caster", "target")'):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(text, ctx)
