"""Native eYq arithmetic: float32, GS.t int overflow and eVt short override."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat.combat_polynomial_level_group import (
    native_override,
    runtime_child_level,
)


def fixture(coefficients, level):
    raw = [value for coefficient in coefficients for value in (coefficient, 0)]
    return (
        dict(effect_class=1101, parameter_count=len(coefficients), parameters=raw),
        dict(parameters=list(coefficients)),
        SimpleNamespace(level=level),
    )


class NativePolynomialGroupTests(unittest.TestCase):
    def test_quadratic_uses_actual_container_level(self):
        self.assertEqual(native_override(*fixture([1, 2, 3], 4)), 57)

    def test_native_float32_accumulation_loses_small_middle_term(self):
        self.assertEqual(native_override(*fixture([16777216, 1, -16777216], 1)), 0)

    def test_native_gs_int_power_overflows_before_float_conversion(self):
        self.assertEqual(native_override(*fixture([0, 0, 0, 0, 1], 256)), 0)

    def test_native_math_round_negative_half_rounds_towards_positive(self):
        self.assertEqual(native_override(*fixture([-0.5, 0], 1)), 0)

    def test_native_round_saturates_signed_integer(self):
        self.assertEqual(native_override(*fixture([1e30, 0], 1)), 2147483647)
        self.assertEqual(native_override(*fixture([-1e30, 0], 1)), -2147483648)

    def test_minus_one_override_keeps_actual_parent_level(self):
        self.assertEqual(runtime_child_level(*fixture([-1, 0], 47)), 47)
        self.assertEqual(
            runtime_child_level(*fixture([-1, 0], 47), return_native_override=True), -1
        )

    def test_child_level_signed_short_narrowing(self):
        self.assertEqual(runtime_child_level(*fixture([65536, 0], 47)), 0)
        self.assertEqual(runtime_child_level(*fixture([32768, 0], 47)), -32768)

    def test_unknown_family_parameter_domain_and_level_rejected(self):
        effect, values, invocation = fixture([1, 2], 1)
        for changed in (
            dict(effect, effect_class=1100),
            dict(effect, parameter_count=1),
            dict(effect, parameters=[1]),
        ):
            with self.assertRaises(ValueError):
                native_override(changed, values, invocation)
        with self.assertRaises(ValueError):
            native_override(effect, values, SimpleNamespace(level=32768))

    def test_native_polynomial_route_is_actor_even_if_coefficients_zero(self):
        from wakfu_server.combat.combat_effect_groups import native_group_route

        effect, values, invocation = fixture([0, 0], 1)
        self.assertEqual(native_group_route(effect), "actors")
