import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class TargetConditionTests(unittest.TestCase):
    def test_target_identity_rebinding_distinct_from_caster(self):
        for identity in (-7, 8):
            context = ConditionContext(
                {
                    "caster": ConditionActor(actor_id=7),
                    "target": ConditionActor(actor_id=identity),
                }
            )
            self.assertTrue(
                evaluate_condition(
                    f"GetEffectTarget()=={identity} and GetEffectCaster()==7", context
                )
            )

    def test_proven_null_target_returns_native_zero(self):
        self.assertTrue(
            evaluate_condition(
                "GetEffectTarget()==0", ConditionContext({}, effect_target_absent=True)
            )
        )

    def test_missing_identity_and_missing_resolution_stay_unknown(self):
        for context in (
            ConditionContext({}),
            ConditionContext({"target": ConditionActor()}),
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition("GetEffectTarget()==0", context)

    def test_wrong_arity_or_selector_rejected(self):
        for criteria in ('GetEffectTarget("caster")==7', "GetEffectTarget(1)==7"):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(criteria, ConditionContext({}))
