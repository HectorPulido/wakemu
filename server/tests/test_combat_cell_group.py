import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_cell_group import (
    cell_group_mode,
    select_cell_group,
    selected_height,
)


class CellGroupTests(unittest.TestCase):
    def test_actual_349_metadata_matches_compiled_immutable_raw_definition(self):
        from wakfu_server.combat_static_catalogs import CompiledEffects
        from wakfu_server.combat_cell_group import (
            native_cell_criterion_presence,
            native_cell_group_metadata,
        )

        row = native_cell_group_metadata()["384594"]
        raw = dict(
            effect_class=349,
            area_class=row["area_class"],
            parameters=list(row["raw_parameters"]),
        )
        compiled = CompiledEffects({"384594": raw}, {"effects": {}})
        definition = compiled.effects["384594"]
        self.assertIsInstance(definition["parameters"], tuple)
        invocation = SimpleNamespace(reference=384594)
        self.assertTrue(native_cell_criterion_presence(definition, invocation))
        self.assertTrue(native_cell_criterion_presence(raw, invocation))
        for changed in (
            dict(raw, parameters=[2.0, *raw["parameters"][1:]]),
            dict(raw, area_class="anA"),
        ):
            with self.assertRaisesRegex(ValueError, "matching native eYk"):
                native_cell_criterion_presence(changed, invocation)

    def test_height_uses_mask_index_and_first_native_chunk_without_fallback(self):
        qi = SimpleNamespace(
            x=0, y=0, width=1, masks=[257], aK=lambda x, y: x == y == 0
        )
        surfaces = SimpleNamespace(
            chunks=[
                ((0, 0, 1, 1), {(0, 0): (SimpleNamespace(z=5), SimpleNamespace(z=9))}),
                ((0, 0, 1, 1), {(0, 0): (SimpleNamespace(z=99),)}),
            ]
        )
        self.assertEqual(selected_height(qi, surfaces, 0, 0), 9)
        qi.masks[0] = 258
        self.assertEqual(selected_height(qi, surfaces, 0, 0), -32768)
        with self.assertRaisesRegex(ValueError, "outside"):
            selected_height(qi, surfaces, 1, 0)

    def select(
        self, parameters, cells, condition=lambda cell: True, criterion_present=True
    ):
        return select_cell_group(
            dict(parameters=parameters),
            cells,
            caster_position=(0, 0, 0),
            condition=condition,
            rng=lambda: 0,
            criterion_present=criterion_present,
        )

    def test_native_spiral_orders_and_unknown_order(self):
        cells = ((0, -1, 1), (-1, 0, 2), (0, 1, 3), (1, 0, 4), (0, 0, 5), (2, 0, 6))
        ascending = (cells[4], cells[3], cells[2], cells[1], cells[0], cells[5])
        for order, expected in ((1, ascending), (2, ascending[::-1]), (99, cells)):
            self.assertEqual(
                self.select([6, 0, 0, 0, 0, 0, 0, order], cells).cells, expected
            )

    def test_count_is_cells_and_zero_does_not_mean_empty_population(self):
        cells = ((1, 0, 0), (0, 1, 0))
        for count in (-1, 0):
            result = self.select([count, 0, 0, 0, 0, 0, 0], cells)
            self.assertEqual(result.cells, ())
            self.assertEqual(result.eligible_count, 2)
        self.assertEqual(self.select([1, 0, 0, 0, 0, 0, 0], cells).cells, cells[:1])

    def test_filter_requires_actual_native_criterion_presence(self):
        cells = ((1, 0, 0), (0, 1, 0))
        calls = []

        def condition(cell):
            calls.append(cell)
            return cell == cells[1]

        self.assertEqual(
            self.select([2, 0, 1, 0, 0, 0, 0], cells, condition).cells, cells[1:]
        )
        self.assertEqual(calls, list(cells))
        calls.clear()
        self.assertEqual(
            self.select([2, 0, 1, 0, 0, 0, 0], cells, condition, False).cells, cells
        )
        self.assertEqual(calls, [])

    def test_missing_shuffle_parameter_defaults_enabled_and_unused_parameter_five(self):
        self.assertTrue(cell_group_mode(dict(parameters=[1])).shuffle)
        base = [1, 0, 0, 0, 0, 0, 0, 0]
        other = base[:]
        other[5] = 1
        self.assertEqual(
            cell_group_mode(dict(parameters=base)),
            cell_group_mode(dict(parameters=other)),
        )

    def test_dispatches_cells_then_all_children_without_retaining_selected_actor(self):
        from test_combat_effect_dispatch import effect
        from wakfu_server.combat_conditions import ConditionContext
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            EffectInvocation,
        )

        seen, notifications = [], []
        retention = SimpleNamespace(
            is_subscription=lambda *args: False,
            begin_group=lambda *args: "pending",
            finish_group=lambda pending, **kw: notifications.append((pending, kw)),
            child_level_context=lambda *args, **kw: (20, b""),
            probability_bypassed=lambda *args: False,
        )
        effects = {
            "90": effect(349, (2, 0, 0, 0, 0, 0, 0), children=(91, 92)),
            "91": effect(400),
            "92": effect(400),
        }

        def handler(definition, values, invocation):
            seen.append(invocation)
            return True

        dispatcher = EffectDispatcher(
            effects,
            {400: handler},
            resolve=lambda definition, invocation: (invocation,),
            condition_context=lambda invocation: ConditionContext({}),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: ((1, 0, 2), (0, 1, 3)),
            actor_position=lambda identity: (0, 0, 0),
            group_retention=retention,
            group_random=lambda: 0,
            pt_preflight=lambda *args: True,
        )
        with patch(
            "wakfu_server.combat_cell_group.native_cell_criterion_presence",
            return_value=False,
        ):
            self.assertTrue(
                dispatcher.execute(EffectInvocation(90, 1, 1, 2, (9, 9, 5)))
            )
        self.assertEqual(
            [(row.reference, row.cell, row.target_id, row.level) for row in seen],
            [
                (reference, cell, None, 20)
                for cell in ((1, 0, 2), (0, 1, 3))
                for reference in (91, 92)
            ],
        )
        self.assertEqual(notifications, [("pending", {"notify": True})])


if __name__ == "__main__":
    unittest.main()
