import unittest
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)


class MeleeTriggerTests(unittest.TestCase):
    def test_native_flags_override_actual_distance(self):
        for flags, distance, expected in (
            ([], 2, True),
            ([], 3, False),
            ([23], 100, True),
            ([24], 0, False),
            ([23, 24], 100, True),
        ):
            with self.subTest(flags=flags, distance=distance):
                context = ConditionContext(
                    {},
                    triggering_effect_present=True,
                    triggering_effect_flags=frozenset(flags),
                    triggering_melee_distance=distance,
                )
                self.assertEqual(
                    evaluate_condition("IsTriggeredByMeleeEffect()", context), expected
                )

    def test_absent_unknown_and_constructor(self):
        self.assertFalse(
            evaluate_condition(
                "IsTriggeredByMeleeEffect()",
                ConditionContext({}, triggering_effect_present=False),
            )
        )
        for context in (
            ConditionContext({}),
            ConditionContext({}, triggering_effect_present=True),
            ConditionContext(
                {}, triggering_effect_present=True, triggering_effect_flags=frozenset()
            ),
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition("IsTriggeredByMeleeEffect()", context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsTriggeredByMeleeEffect(1)", ConditionContext({}))
