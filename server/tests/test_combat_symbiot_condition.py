import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class SymbiotConditionTests(unittest.TestCase):
    def test_native_target_or_caster_selection_and_negation(self):
        for caster in (False, True):
            for target in (False, True):
                context = ConditionContext(
                    {
                        "caster": ConditionActor(
                            is_native_ehg=True, is_summoned_from_symbiot=caster
                        ),
                        "target": ConditionActor(
                            is_native_ehg=True, is_summoned_from_symbiot=target
                        ),
                    }
                )
                for selector, expected in (
                    ("target", target),
                    ("TARGET", target),
                    ("caster", caster),
                    ("eventtarget", caster),
                    ("", caster),
                ):
                    expression = 'IsSummonedFromSymbiot("' + selector + '")'
                    self.assertEqual(evaluate_condition(expression, context), expected)
                    self.assertEqual(
                        evaluate_condition("!" + expression, context), not expected
                    )

    def test_missing_creation_source_is_unknown_not_false(self):
        with self.assertRaisesRegex(UnknownCondition, "dTC"):
            evaluate_condition(
                'IsSummonedFromSymbiot("target")',
                ConditionContext({"target": ConditionActor(is_native_ehg=True)}),
            )
        for expression in (
            "IsSummonedFromSymbiot()",
            "IsSummonedFromSymbiot(1)",
            'IsSummonedFromSymbiot("target", "caster")',
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ConditionContext({}))

    def test_explicit_null_native_target_is_false(self):
        self.assertFalse(
            evaluate_condition(
                'IsSummonedFromSymbiot("target")',
                ConditionContext({}, effect_target_absent=True),
            )
        )
