import unittest

from wakfu_server.combat_execution_count import native_execution_count


class NativeExecutionCountTests(unittest.TestCase):
    def test_level_scaled_budget_and_unlimited(self):
        self.assertEqual(native_execution_count(0, 1.0, 10), 10)
        self.assertEqual(native_execution_count(2, 0.25, 7), 3)
        self.assertEqual(native_execution_count(-2, None, 7), -1)

    def test_java_float_rounding_and_int_not_short(self):
        self.assertEqual(native_execution_count(1, 16777216.0, 1), 16777216)
        self.assertEqual(native_execution_count(0, 2.0, 32767), 65534)
        self.assertEqual(native_execution_count(0, float("inf"), 1), 2147483647)
        self.assertEqual(native_execution_count(0, float("nan"), 1), 0)

    def test_unknown_coefficient_and_invalid_level_rejected(self):
        for args in ((0, None, 10), (0, True, 10), (0, 1, 32768), (True, 1, 1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                native_execution_count(*args)
