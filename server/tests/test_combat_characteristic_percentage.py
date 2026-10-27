import unittest
from wakfu_server.combat_characteristic_percentage import characteristic_percentage
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
)


class CharacteristicPercentageTests(unittest.TestCase):
    def test_moon_threshold_uses_native_integer_percentage(self):
        for hp, expected in ((1000, True), (1014, True), (1049, True), (1050, False)):
            with self.subTest(hp=hp):
                context = ConditionContext(
                    {
                        "caster": ConditionActor(
                            characteristics={"HP": hp},
                            characteristic_maxima={"HP": 5000},
                        )
                    }
                )
                self.assertEqual(characteristic_percentage(hp, 5000) <= 20, expected)
                self.assertEqual(
                    evaluate_condition('GetCharacInPct("HP")<=20', context), expected
                )

    def test_java_nonfinite_floor_and_saturating_then_wrapping_cast(self):
        for current, maximum, expected in (
            (0, 0, -1),
            (1, 0, 2147483647),
            (-1, 0, 2147483647),
            (1, 3, 33),
            (-1, 3, -34),
            (1, -3, -34),
            (2147483647, 1, 2147483647),
            (-2147483648, 1, 2147483647),
        ):
            with self.subTest(current=current, maximum=maximum):
                self.assertEqual(characteristic_percentage(current, maximum), expected)

    def test_all_parser_aliases_use_actual_selected_actor_current_and_maximum(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    characteristics={"HP": 1}, characteristic_maxima={"HP": 3}
                ),
                "target": ConditionActor(
                    characteristics={"HP": -1}, characteristic_maxima={"HP": 3}
                ),
            }
        )
        for name in ("GetCharacInPct", "GetCharacPct", "GetCharacteristicPct"):
            with self.subTest(name=name):
                self.assertTrue(evaluate_condition(f'{name}("HP")==33', context))
                self.assertTrue(
                    evaluate_condition(f'{name}("HP","target")==-34', context)
                )

    def test_parser_zero_maximum_matches_native_finite_integer_result(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    characteristics={"HP": 0}, characteristic_maxima={"HP": 0}
                )
            }
        )
        self.assertTrue(evaluate_condition('GetCharacInPct("HP")==-1', context))
        absent = ConditionContext({}, effect_target_absent=True)
        self.assertTrue(evaluate_condition('GetCharacInPct("HP","target")==-1', absent))
