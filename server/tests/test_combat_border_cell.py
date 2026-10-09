import unittest

from wakfu_server.combat_condition_border import border_cell_result
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class NativeBorderCellConditionTests(unittest.TestCase):
    def test_native_qi_border_bit_sentinel_and_rectangle_semantics(self):
        arena = {
            "x": -1,
            "y": 4,
            "width": 3,
            "height": 2,
            "cell_masks": [128, 0, -257, 384, 256, -1],
        }
        self.assertEqual(border_cell_result(arena, -1, 4), 0)
        self.assertEqual(border_cell_result(arena, -1, 5), 0)
        for x, y in ((0, 4), (1, 4), (0, 5), (99, 99)):
            with self.subTest(x=x, y=y):
                self.assertEqual(border_cell_result(arena, x, y), -1)

    def test_native_eor_is_boolean_with_target_only_selector(self):
        calls = []

        def query(selector):
            calls.append(selector)
            return {"caster": 0, "target": -1}[selector]

        context = ConditionContext({}, border_cell_query=query)
        self.assertTrue(evaluate_condition('IsOnBorderCell("caster")', context))
        self.assertFalse(evaluate_condition('IsOnBorderCell("TaRgEt")', context))
        self.assertTrue(
            evaluate_condition('IsOnBorderCell("casterController")', context)
        )
        self.assertTrue(evaluate_condition('not IsOnBorderCell("target")', context))
        self.assertTrue(
            evaluate_condition(
                'IsOnBorderCell("caster") and not IsOnBorderCell("target")', context
            )
        )
        self.assertEqual(
            calls, ["caster", "target", "caster", "target", "caster", "target"]
        )

    def test_missing_query_malformed_signature_and_invalid_result_reject(self):
        with self.assertRaisesRegex(UnknownCondition, "QI border-cell authority"):
            evaluate_condition('IsOnBorderCell("caster")', ConditionContext({}))
        for expression in (
            "IsOnBorderCell()",
            "IsOnBorderCell(1)",
            'IsOnBorderCell("caster", "target")',
            'IsOnBorderCell("caster") == 0',
        ):
            with self.subTest(expression=expression), self.assertRaises(
                UnknownCondition
            ):
                evaluate_condition(
                    expression, ConditionContext({}, border_cell_query=lambda *_: 0)
                )
        with self.assertRaisesRegex(UnknownCondition, "Invalid native eOr"):
            evaluate_condition(
                'IsOnBorderCell("caster")',
                ConditionContext({}, border_cell_query=lambda *_: True),
            )
        with self.assertRaises(ValueError):
            border_cell_result(
                {"x": 0, "y": 0, "width": 1, "height": 1, "cell_masks": [True]}, 0, 0
            )
