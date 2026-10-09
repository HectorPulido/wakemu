import unittest
from wakfu_server.combat_effect_groups import (
    native_group_cell_mode,
    native_group_route,
    UnsupportedEffectGroup,
)


class NativeGroupCellRoutingTests(unittest.TestCase):
    def test_actual_inherited_runner_matrix_uses_raw_value(self):
        for family in (330, 844, 910, 912, 913, 999, 1020, 1047):
            for count in (2, 3):
                for raw in (0, 1, 2, 10):
                    effect = dict(
                        effect_class=family,
                        parameter_count=count,
                        parameters=[0, 0, 0, 0, raw, 99],
                    )
                    self.assertEqual(
                        native_group_cell_mode(effect), count >= 3 and raw == 0
                    )

    def test_unknown_runner_and_invalid_contract_not_misrouted(self):
        for count, raw, expected in (
            (0, None, "actors"),
            (1, None, "actors"),
            (2, 1, "actors"),
            (2, 0, "cell"),
            (2, 2, "none"),
            (3, -1, "none"),
        ):
            effect = {"effect_class": 341, "parameter_count": count}
            if raw is not None:
                effect["parameters"] = [17, raw, 99]
            with self.subTest(count=count, raw=raw):
                self.assertEqual(native_group_route(effect), expected)
                self.assertEqual(native_group_cell_mode(effect), expected == "cell")
        with self.assertRaises(UnsupportedEffectGroup):
            native_group_route({"effect_class": 341, "parameter_count": 2})
        with self.assertRaises(UnsupportedEffectGroup):
            native_group_cell_mode(
                dict(effect_class=330, parameter_count=3, parameters=[0] * 4)
            )
        self.assertEqual(
            native_group_route(
                dict(
                    effect_class=999, parameter_count=3, parameters=[0, 0, 0, 0, 10, 0]
                )
            ),
            "none",
        )
        self.assertFalse(
            native_group_cell_mode(
                dict(effect_class=330, parameter_count=3, parameters=[0, 0, 0, 0, 2, 0])
            )
        )
