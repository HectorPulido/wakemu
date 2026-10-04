import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)


class StateLevelConditionTests(unittest.TestCase):
    def test_first_ordered_state_level_and_default_caster(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(state_levels=((12, 3), (12, 9))),
                "target": ConditionActor(state_levels=((12, 8),)),
            }
        )
        self.assertTrue(evaluate_condition("GetStateLevel(12) == 3", context))
        self.assertTrue(evaluate_condition('GetStateLevel(12,"target") == 8', context))

    def test_missing_state_is_minus_one_but_unknown_context_rejects(self):
        self.assertTrue(
            evaluate_condition(
                "GetStateLevel(12) == -1",
                ConditionContext({"caster": ConditionActor(state_levels=())}),
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetStateLevel(12) == -1",
                ConditionContext({"caster": ConditionActor()}),
            )

    def test_invalid_selector_rejected_even_short_circuit(self):
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'True or GetStateLevel(12,"all") == 0', ConditionContext({})
            )

    def test_actual_combined_level_state_arithmetic(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    state_levels=((3617, 124),), effective_level=200
                ),
                "target": ConditionActor(state_levels=(), effective_level=1),
            }
        )
        self.assertTrue(
            evaluate_condition("GetStateLevel(3617) < GetLevel() * 2", context)
        )
        self.assertTrue(evaluate_condition('GetLevel("target") == 1', context))
