import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)


class IsSummonTests(unittest.TestCase):
    def test_case_insensitive_rebound_target_uses_explicit_native_fact(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(is_summon=False),
                "target": ConditionActor(is_summon=True),
                "castercontroller": ConditionActor(is_summon=False),
            }
        )
        self.assertTrue(evaluate_condition('IsSummon("TaRgEt")', context))
        self.assertFalse(evaluate_condition('IsSummon("caster")', context))
        self.assertFalse(evaluate_condition('IsSummon("casterController")', context))
        self.assertFalse(evaluate_condition('IsSummon("invalid")', context))

    def test_known_null_and_unknown_authority_are_distinct(self):
        self.assertFalse(
            evaluate_condition(
                'IsSummon("target")', ConditionContext({}, effect_target_absent=True)
            )
        )
        self.assertFalse(
            evaluate_condition(
                'IsSummon("triggeringCaster")',
                ConditionContext({}, triggering_effect_present=False),
            )
        )
        for context in (
            ConditionContext({}),
            ConditionContext({"target": ConditionActor(is_character=False)}),
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition('IsSummon("target")', context)

    def test_signature_one_string_no_default(self):
        for expression in (
            "IsSummon()",
            "IsSummon(1)",
            'IsSummon("caster", "target")',
            "True or IsSummon()",
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ConditionContext({}))
