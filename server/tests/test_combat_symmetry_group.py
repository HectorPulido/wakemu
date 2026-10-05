import unittest
from types import SimpleNamespace
from wakfu_server.combat_symmetry_group import symmetry_xy, symmetry_center
from wakfu_server.combat_effect_groups import native_group_route
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_conditions import ConditionContext
from test_combat_effect_dispatch import effect


class SymmetryGroupTests(unittest.TestCase):
    def test_native_rotation_height_overflow_and_missing_column(self):
        terrain = SimpleNamespace(walkable={(-2, 6, -8), (-1, -1, 0), (6, 0, 6)})
        for angle, expected in [(0, (-2, 6, -8)), (1, (-1, -1, 0)), (2, (6, 0, 6))]:
            self.assertEqual(
                symmetry_center(terrain, [0, angle], (2, 3, 100), (5, 7, -10)), expected
            )
        self.assertEqual(symmetry_xy([0, 1], (2147483647, 0), (-1, 0)), (-1, 0))
        self.assertIsNone(symmetry_center(terrain, [0], (0, 0, 0), (7, 7, 0)))
        with self.assertRaises(ValueError):
            symmetry_center(
                SimpleNamespace(walkable={(-1, -1, 0), (-1, -1, 1)}),
                [0],
                (2, 3, 0),
                (5, 7, 0),
            )

    def test_pivot_exact_one_and_default_angle(self):
        self.assertEqual(symmetry_xy([1], (2, 3), (5, 7)), (8, 11))
        self.assertEqual(symmetry_xy([2], (2, 3), (5, 7)), (-1, -1))
        self.assertEqual(symmetry_xy([0, 8], (2, 3), (5, 7)), (-1, -1))
        self.assertEqual(native_group_route(effect(352, (1,))), "cell")

    def dispatcher(self, cells):
        selected = []
        dispatcher = EffectDispatcher(
            {
                "90": effect(352, (1,), children=(91, 92)),
                "91": effect(400),
                "92": effect(400),
            },
            {400: lambda *args: True},
            resolve=lambda e, i: (selected.append(i) or (i,)),
            condition_context=lambda i: ConditionContext({}),
            probability_accepts=lambda *a: True,
            group_cells=lambda *a: cells,
            actor_position=lambda i: (0, 0, 0),
        )
        return dispatcher, selected

    def test_transformed_cells_children_order_null_target_and_preserved_source(self):
        dispatcher, selected = self.dispatcher(((8, 11, 4),))
        self.assertTrue(
            dispatcher.execute(EffectInvocation(90, 20, 7, None, (5, 7, 0)))
        )
        children = [i for i in selected if i.reference != 90]
        self.assertEqual(
            [(i.reference, i.caster_id, i.target_id, i.cell) for i in children],
            [(91, 7, None, (8, 11, 4)), (92, 7, None, (8, 11, 4))],
        )

    def test_missing_transformed_center_executes_no_children(self):
        dispatcher, selected = self.dispatcher(())
        self.assertFalse(
            dispatcher.execute(EffectInvocation(90, 20, 7, None, (5, 7, 0)))
        )
        self.assertEqual([i.reference for i in selected], [90])

    def test_common_group_codec_matches_original_eya_without_additional_data(self):
        from wakfu_server.combat_retained_runtime import group_payload
        from wakfu_server.combat_native_timing_context import native_time_payload

        self.assertEqual(
            group_payload(
                uid=901,
                base_uid=901,
                generic_effect=123,
                caster_id=7,
                target_id=None,
                cell=(2, -3, 4),
                container_type=None,
                container_id=None,
                timing_payload=native_time_payload(),
            ).hex(),
            "088507108507187b20002a0f080210fdffffffffffffffff01180430075a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012800",
        )

    def test_unsupported_later_child_rolls_back_prior_effect(self):
        from wakfu_server.combat_effect_dispatch import (
            run_effect_transaction,
            UnsupportedEffectExecution,
        )
        from contextlib import nullcontext

        original = SimpleNamespace(hp=20, effect_resolution=lambda: nullcontext())
        effects = {
            "90": effect(352, (1,), children=(91, 92)),
            "91": effect(400),
            "92": effect(123456),
        }

        def factory(preview):
            def apply(*args):
                preview.hp -= 5
                return True

            return EffectDispatcher(
                effects,
                {400: apply},
                resolve=lambda e, i: (i,),
                condition_context=lambda i: ConditionContext({}),
                probability_accepts=lambda *a: True,
                group_cells=lambda *a: ((8, 11, 4),),
                actor_position=lambda i: (0, 0, 0),
            )

        with self.assertRaises(UnsupportedEffectExecution):
            run_effect_transaction(
                original, [EffectInvocation(90, 20, 7, None, (5, 7, 0))], factory
            )
        self.assertEqual(original.hp, 20)
