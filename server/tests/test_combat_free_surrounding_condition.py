"""eMp native four-cell checks and criterion defaults."""
import unittest
from wakfu_server.combat.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat.combat_free_surrounding_condition import (
    native_free_surrounding_cell,
)


class FreeSurroundingConditionTests(unittest.TestCase):
    def test_each_cardinal_neighbor_can_satisfy_native_predicate(self):
        for free in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            with self.subTest(free=free):
                self.assertTrue(
                    native_free_surrounding_cell(
                        (0, 0, 8),
                        terrain_free=lambda x, y: (x, y) == free,
                        first_obstacle=lambda x, y: False,
                    )
                )

    def test_diagonal_and_origin_do_not_count(self):
        self.assertFalse(
            native_free_surrounding_cell(
                (0, 0, 0),
                terrain_free=lambda x, y: (x, y) in {(0, 0), (1, 1)},
                first_obstacle=lambda x, y: False,
            )
        )

    def test_any_registered_qk_blocks_even_when_terrain_accepts(self):
        self.assertFalse(
            native_free_surrounding_cell(
                (0, 0, 0),
                terrain_free=lambda x, y: True,
                first_obstacle=lambda x, y: True,
            )
        )

    def test_native_q_and_r_terrain_modes_are_distinct(self):
        from wakfu_server.combat.combat_qi_snapshot import NativeQISnapshot

        qi = NativeQISnapshot(dict(x=-1, y=-1, width=3, height=3, cell_masks=[128] * 9))
        self.assertFalse(
            native_free_surrounding_cell(
                (0, 0, 0), terrain_free=qi.Q, first_obstacle=lambda x, y: False
            )
        )
        self.assertTrue(
            native_free_surrounding_cell(
                (0, 0, 0), terrain_free=qi.R, first_obstacle=lambda x, y: False
            )
        )

    def test_native_obstacle_check_precedes_terrain(self):
        def terrain(*args):
            self.fail("Native eMp must skip terrain for occupied cells")

        self.assertFalse(
            native_free_surrounding_cell(
                (0, 0, 0), terrain_free=terrain, first_obstacle=lambda x, y: True
            )
        )

    def test_coordinate_overflow_uses_native_int32(self):
        probes = []
        native_free_surrounding_cell(
            ((1 << 31) - 1, 0, 0),
            terrain_free=lambda x, y: False,
            first_obstacle=lambda x, y: probes.append((x, y)) or False,
        )
        self.assertEqual(probes[0], (-(1 << 31), 0))

    def test_defaults_and_both_literal_boolean_flags(self):
        calls = []
        context = ConditionContext(
            {},
            free_surrounding_cell_query=lambda strict, target: calls.append(
                (strict, target)
            )
            or True,
        )
        for criterion in (
            "HasFreeSurroundingCell()",
            "HasFreeSurroundingCell(True)",
            "HasFreeSurroundingCell(False, False)",
        ):
            self.assertTrue(evaluate_condition(criterion, context))
        self.assertEqual(calls, [(False, True), (True, True), (False, False)])

    def test_unknown_authority_and_malformed_signatures_remain_unknown(self):
        with self.assertRaises(UnknownCondition):
            evaluate_condition("HasFreeSurroundingCell()", ConditionContext({}))
        context = ConditionContext({}, free_surrounding_cell_query=lambda *a: None)
        with self.assertRaises(UnknownCondition):
            evaluate_condition("HasFreeSurroundingCell()", context)
        for criterion in (
            "HasFreeSurroundingCell(1)",
            'HasFreeSurroundingCell("target")',
            "True or HasFreeSurroundingCell(False, True, True)",
        ):
            with self.subTest(criterion=criterion), self.assertRaises(UnknownCondition):
                evaluate_condition(criterion, context)


if __name__ == "__main__":
    unittest.main()
