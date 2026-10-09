import unittest

from wakfu_server.combat_casting_alignment import native_casting_alignment
from wakfu_server.combat_conditions import UnknownCondition


class NativeCastingAlignmentTests(unittest.TestCase):
    def test_selected_linear_and_diagonal_flags_are_independent(self):
        self.assertTrue(
            native_casting_alignment(
                (0, 0),
                (4, 3),
                linear=False,
                diagonal=False,
                linear_path=False,
                path_option=False,
            )
        )
        self.assertTrue(
            native_casting_alignment(
                (0, 0),
                (0, 3),
                linear=True,
                diagonal=False,
                linear_path=False,
                path_option=False,
            )
        )
        self.assertFalse(
            native_casting_alignment(
                (0, 0),
                (4, 3),
                linear=True,
                diagonal=False,
                linear_path=False,
                path_option=False,
            )
        )
        self.assertTrue(
            native_casting_alignment(
                (0, 0),
                (4, 4),
                linear=False,
                diagonal=True,
                linear_path=False,
                path_option=False,
            )
        )
        self.assertFalse(
            native_casting_alignment(
                (0, 0),
                (4, 3),
                linear=False,
                diagonal=True,
                linear_path=False,
                path_option=False,
            )
        )

    def test_linear_path_uses_only_selected_path_option(self):
        calls = []

        def path_query(path_option):
            calls.append(path_option)
            return False

        self.assertFalse(
            native_casting_alignment(
                (0, 0),
                (0, 3),
                linear=True,
                diagonal=False,
                linear_path=True,
                path_option=True,
                path_query=path_query,
            )
        )
        self.assertEqual(calls, [True])
        with self.assertRaisesRegex(UnknownCondition, "Sn casting traversal"):
            native_casting_alignment(
                (0, 0),
                (0, 3),
                linear=True,
                diagonal=False,
                linear_path=True,
                path_option=False,
            )
        with self.assertRaisesRegex(UnknownCondition, "Sn casting traversal result"):
            native_casting_alignment(
                (0, 0),
                (0, 3),
                linear=True,
                diagonal=False,
                linear_path=True,
                path_option=False,
                path_query=lambda _path_option: None,
            )

    def test_diagonal_uses_java_int_wrap_and_missing_flags_reject(self):
        int_min = -(1 << 31)
        self.assertTrue(
            native_casting_alignment(
                (0, 0),
                (int_min, int_min),
                linear=False,
                diagonal=True,
                linear_path=False,
                path_option=False,
            )
        )
        self.assertFalse(
            native_casting_alignment(
                (0, 0),
                (int_min, 0),
                linear=False,
                diagonal=True,
                linear_path=False,
                path_option=False,
            )
        )
        with self.assertRaisesRegex(ValueError, "selected native static casting flags"):
            native_casting_alignment(
                (0, 0),
                (0, 3),
                linear=1,
                diagonal=False,
                linear_path=False,
                path_option=False,
            )
        with self.assertRaisesRegex(ValueError, "static casting XY coordinates"):
            native_casting_alignment(
                (0, 0),
                (None, 3),
                linear=False,
                diagonal=True,
                linear_path=False,
                path_option=False,
            )


if __name__ == "__main__":
    unittest.main()
