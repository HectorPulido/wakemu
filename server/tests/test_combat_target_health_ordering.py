"""Pure faI operands preserve Java float32, missing PA and tie semantics."""
import unittest
from wakfu_server.combat_target_health_ordering import (
    NativeHealthOperand as HP,
    compare_native_health,
)


class HealthOrderingTests(unittest.TestCase):
    def test_percentage_ties_preserve_equal_comparator(self):
        self.assertEqual(compare_native_health(HP(True, 1, 2), HP(True, 2, 4)), 0)
        self.assertEqual(
            compare_native_health(
                HP(True, 16777217, 16777216), HP(True, 16777216, 16777217)
            ),
            0,
        )

    def test_absence_order_is_exact_native_even_both_absent(self):
        self.assertEqual(compare_native_health(HP(False), HP(True, 1, 2)), 1)
        self.assertEqual(compare_native_health(HP(True, 1, 2), HP(False)), -1)
        self.assertEqual(compare_native_health(HP(False), HP(False)), 1)

    def test_java_nan_infinity_and_signed_zero(self):
        self.assertEqual(compare_native_health(HP(True, 0, 0), HP(True, 1, 0)), 1)
        self.assertEqual(compare_native_health(HP(True, -1, 0), HP(True, 1, 0)), -1)
        self.assertEqual(compare_native_health(HP(True, 0, -1), HP(True, 0, 1)), -1)
        self.assertEqual(compare_native_health(HP(True, 0, 0), HP(True, 0, 0)), 0)

    def test_unknown_presence_or_container_values_rejected(self):
        for args in [
            (None,),
            (True,),
            (True, 1, None),
            (True, True, 1),
            (True, 1 << 31, 1),
            (False, 0, 0),
        ]:
            with self.assertRaises(ValueError):
                HP(*args)
        with self.assertRaises(ValueError):
            compare_native_health(object(), HP(False))
