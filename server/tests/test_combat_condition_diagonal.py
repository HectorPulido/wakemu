"""Original eNY differs from static fcj's absolute-displacement comparison."""
import unittest
from wakfu_server.combat_condition_diagonal import native_diagonal
from wakfu_server.combat_condition_alignment import native_alignment
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class NativeDiagonalTests(unittest.TestCase):
    def test_original_java_oracle_rows(self):
        for source, target, expected in (
            ((0, 0), (1, 1), True),
            ((0, 0), (1, 2), False),
            ((0, 0), (46341, 46342), True),
            ((0, 0), (-2147483648, 2147483647), True),
            ((0, 0, 0), (0, 0, 7), True),
            ((2147483647, 0), (-2147483648, 1), True),
            ((0, 0), (46340, 46341), False),
        ):
            self.assertIs(native_diagonal(source, target), expected)

    def test_explicit_native_null_is_false_invalid_metadata_is_unknown(self):
        self.assertFalse(native_diagonal(None, (1, 1)))
        self.assertFalse(native_diagonal((1, 1), None))
        for invalid in ((True, 0), (2147483648, 0), (0,), "cell"):
            with self.assertRaises(ValueError):
                native_diagonal(invalid, (0, 0))

    def test_empty_signature_and_explicit_boolean_authority(self):
        for value in (True, False):
            context = ConditionContext({}, is_in_diagonal=value)
            self.assertIs(evaluate_condition("IsInDiagonal()", context), value)
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsInDiagonal()", ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'IsInDiagonal("target")', ConditionContext({}, is_in_diagonal=True)
            )


class NativeAlignmentTests(unittest.TestCase):
    def test_original_axis_equality_and_explicit_null(self):
        for source, target, expected in (
            ((0, 0), (0, 7), True),
            ((0, 0), (4, 0), True),
            ((0, 0), (4, 7), False),
            ((0, 0, 1), (0, 7, 9), True),
            ((0, 0), None, False),
        ):
            with self.subTest(source=source, target=target):
                self.assertIs(native_alignment(source, target), expected)

    def test_malformed_coordinate_is_not_native_null(self):
        for malformed in ((True, 0), (0,), "cell"):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                native_alignment((0, 0), malformed)

    def test_alignment_condition_uses_explicit_boolean_authority(self):
        for value in (True, False):
            context = ConditionContext({}, is_in_alignment=value)
            self.assertIs(evaluate_condition("IsInAlignment()", context), value)
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsInAlignment()", ConditionContext({}))
