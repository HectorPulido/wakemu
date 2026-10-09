import unittest

from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class NativeBreedNullTests(unittest.TestCase):
    def test_proven_null_and_nonfighter_are_false_without_inventing_breed(self):
        expression = 'IsBreed("Cra", "target")'
        contexts = (
            ConditionContext({}, null_actor_aliases=frozenset({"target"})),
            ConditionContext({}, effect_target_absent=True),
            ConditionContext({"target": ConditionActor(is_native_fighter=False)}),
        )
        for context in contexts:
            with self.subTest(context=context):
                self.assertFalse(evaluate_condition(expression, context))
                self.assertTrue(evaluate_condition("not " + expression, context))

    def test_unknown_selection_and_real_fighter_missing_breed_remain_unknown(self):
        for context in (
            ConditionContext({}),
            ConditionContext({"target": ConditionActor(is_native_fighter=True)}),
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition('IsBreed("Cra", "target")', context)

    def test_last_selector_still_wins_before_null_selection(self):
        context = ConditionContext(
            {"caster": ConditionActor(breed_id=9, is_native_fighter=True)},
            null_actor_aliases=frozenset({"target"}),
        )
        self.assertFalse(
            evaluate_condition('IsBreed("Cra", "caster", "target")', context)
        )
        self.assertTrue(
            evaluate_condition('IsBreed("Cra", "target", "caster")', context)
        )
