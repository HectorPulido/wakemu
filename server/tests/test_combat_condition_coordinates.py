import unittest
from wakfu_server.combat_condition_coordinates import native_coordinate
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class NativeCoordinateTests(unittest.TestCase):
    def test_signed_axes_and_native_null_sentinel(self):
        self.assertEqual(native_coordinate("x", (-2147483648, 7, -1)), -2147483648)
        self.assertEqual(native_coordinate("z", (2, 7, -32768)), -32768)
        self.assertEqual(native_coordinate("y", None), -(1 << 63))
        with self.assertRaises(ValueError):
            native_coordinate("z", (2, 7, 32768))

    def test_selectors_follow_native_constructor_not_generic_actor_selector(self):
        positions = {"caster": (-12, 9, -1), "target": (4, -7, 2)}
        context = ConditionContext(
            {},
            coordinate_query=lambda axis, selector: native_coordinate(
                axis, positions[selector]
            ),
        )
        for expression in (
            "GetX() == -12",
            'GetX("anything") == -12',
            'GetY("TARGET") == -7',
            'GetZ("target") == 2',
        ):
            self.assertTrue(evaluate_condition(expression, context), expression)

    def test_missing_authority_and_invalid_signatures_reject_even_short_circuited(self):
        for expression in (
            "GetX() == 0",
            "True or GetX(1) == 0",
            'False and GetY("target", "caster") == 0',
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ConditionContext({}))


if __name__ == "__main__":
    unittest.main()
