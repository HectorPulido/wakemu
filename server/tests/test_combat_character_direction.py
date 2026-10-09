import unittest

from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class NativeCharacterDirectionTests(unittest.TestCase):
    def test_native_enum_values_and_selector_contract(self):
        for direction in (-1, *range(10)):
            context = ConditionContext(
                {
                    "caster": ConditionActor(direction=direction),
                    "target": ConditionActor(direction=(direction + 1) % 8),
                }
            )
            self.assertTrue(
                evaluate_condition(f"GetCharacterDirection() == {direction}", context)
            )
            self.assertTrue(
                evaluate_condition(
                    f'GetCharacterDirection("TaRgEt") == {(direction + 1) % 8}',
                    context,
                )
            )
            self.assertTrue(
                evaluate_condition(
                    f'GetCharacterDirection("castercontroller") == {direction}',
                    context,
                )
            )

    def test_native_null_target_and_non_egj_return_minus_one(self):
        self.assertTrue(
            evaluate_condition(
                'GetCharacterDirection("target") == -1',
                ConditionContext(
                    {"caster": ConditionActor(direction=3)},
                    effect_target_absent=True,
                ),
            ),
        )

    def test_explicit_cell_requires_native_qi_fighter_lookup_even_with_a_fighter_there(
        self,
    ):
        for actors in (
            {"caster": ConditionActor(direction=3)},
            {
                "caster": ConditionActor(direction=3),
                "target": ConditionActor(direction=6),
            },
        ):
            with self.subTest(actors=actors), self.assertRaisesRegex(
                UnknownCondition, "QI fighter lookup"
            ):
                evaluate_condition(
                    'GetCharacterDirection("target") == -1',
                    ConditionContext(
                        actors,
                        effect_target_absent=True,
                        target_cell_is_explicit=True,
                    ),
                )
        self.assertTrue(
            evaluate_condition(
                'GetCharacterDirection("target") == -1',
                ConditionContext(
                    {
                        "caster": ConditionActor(direction=3),
                        "target": ConditionActor(is_native_fighter=False),
                    }
                ),
            ),
        )

    def test_unknown_direction_and_unresolved_actor_remain_unknown(self):
        with self.assertRaisesRegex(UnknownCondition, "direction"):
            evaluate_condition(
                "GetCharacterDirection() == 1",
                ConditionContext({"caster": ConditionActor(is_native_fighter=True)}),
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'GetCharacterDirection("target") == 1',
                ConditionContext({"caster": ConditionActor(direction=2)}),
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetCharacterDirection() == 1",
                ConditionContext({"caster": ConditionActor(direction=10)}),
            )

    def test_signature_validation_is_strict(self):
        for expression in (
            "GetCharacterDirection(1)",
            'GetCharacterDirection("target", "caster")',
        ):
            with self.subTest(expression=expression), self.assertRaises(
                UnknownCondition
            ):
                evaluate_condition(expression + " == 0", ConditionContext({}))
