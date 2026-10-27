import unittest
from types import SimpleNamespace
from wakfu_server.combat_group_cells import ordered_offsets, group_cells
from wakfu_server.combat_effect_targets import UnsupportedEffectArea, area_offsets
from wakfu_server.combat_effect_groups import decode_group_mode, execute_ordered_group
from wakfu_server.spell_audit import catalog


class NativeGroupCellTests(unittest.TestCase):
    def test_cross_ring_native_order_and_empty_center(self):
        effect = dict(area_class="any", area_native="crossRing-1-3")
        expected = (
            (0, -1),
            (0, -2),
            (0, -3),
            (0, 1),
            (0, 2),
            (0, 3),
            (1, 0),
            (2, 0),
            (3, 0),
            (-1, 0),
            (-2, 0),
            (-3, 0),
        )
        self.assertEqual(ordered_offsets(effect), expected)
        fight = SimpleNamespace(
            walkable={(x, y, 7) for x, y in expected} | {(0, 0, 7), (1, 1, 7)}
        )
        self.assertEqual(
            group_cells(fight, effect, (0, 0, 0)), tuple((x, y, 7) for x, y in expected)
        )

    def test_native_jar_area_order_fixtures(self):
        self.assertEqual(
            ordered_offsets(dict(area_class="anu", area_native="circle-2")),
            (
                (-2, 0),
                (-1, -1),
                (-1, 0),
                (-1, 1),
                (0, -2),
                (0, -1),
                (0, 0),
                (0, 1),
                (0, 2),
                (1, -1),
                (1, 0),
                (1, 1),
                (2, 0),
            ),
        )
        self.assertEqual(
            ordered_offsets(dict(area_class="anH", area_native="ring-1-2")),
            (
                (0, 1),
                (0, -1),
                (0, 2),
                (0, -2),
                (1, 0),
                (-1, 0),
                (1, 1),
                (1, -1),
                (-1, 1),
                (-1, -1),
                (2, 0),
                (-2, 0),
            ),
        )
        self.assertEqual(
            ordered_offsets(dict(area_class="anw", area_native="cross-h1b1-g1d1")),
            ((0, 0), (0, -1), (0, 1), (1, 0), (-1, 0)),
        )
        self.assertEqual(
            ordered_offsets(dict(area_class="anw", area_native="cross-h1b2-g1d1")),
            ((0, 0), (0, -1), (0, 1), (1, 0), (-1, 0), (-2, 0)),
        )

    def test_asymmetric_cross_keeps_each_arm_and_original_cell_order(self):
        effect = dict(area_class="anw", area_native="cross-h2b3-g1d4")
        expected = (
            (0, 0),
            (0, -1),
            (0, 1),
            (0, 2),
            (0, 3),
            (0, 4),
            (1, 0),
            (2, 0),
            (-1, 0),
            (-2, 0),
            (-3, 0),
        )
        self.assertEqual(ordered_offsets(effect), expected)
        self.assertEqual(frozenset(expected), area_offsets(effect))
        fight = SimpleNamespace(walkable={(x + 7, y - 4, 9) for x, y in expected})
        self.assertEqual(
            group_cells(fight, effect, (7, -4, 0)),
            tuple((x + 7, y - 4, 9) for x, y in expected),
        )

    def test_cross_nonpositive_arms_preserve_native_center_and_other_arms(self):
        effect = dict(area_class="anw", area_native="cross-h-2b0-g2d-1")
        self.assertEqual(ordered_offsets(effect), ((0, 0), (0, -1), (0, -2)))
        self.assertEqual(frozenset(ordered_offsets(effect)), area_offsets(effect))

    def test_actual_spirit_8497_cell_groups_preserve_the_long_native_arms(self):
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        effects = npc_runtime_catalog(imported=True).effects
        expected = (
            (0, 0),
            *((0, -n) for n in range(1, 31)),
            *((0, n) for n in range(1, 31)),
            (1, 0),
            (-1, 0),
        )
        for reference in (411047, 411049):
            with self.subTest(reference=reference):
                effect = effects[str(reference)]
                self.assertEqual(
                    (effect["area_class"], effect["area_native"]),
                    ("anw", "cross-h1b1-g30d30"),
                )
                self.assertEqual(ordered_offsets(effect), expected)
                self.assertEqual(frozenset(expected), area_offsets(effect))
                fight = SimpleNamespace(
                    walkable={
                        (-7, -7, -1),
                        (-7, -6, -1),
                        (-7, 2, -1),
                        (-6, -7, -1),
                        (-8, -7, -1),
                        (-5, -7, -1),
                    }
                )
                self.assertEqual(
                    group_cells(fight, effect, (-7, -7, -1)),
                    (
                        (-7, -7, -1),
                        (-7, -6, -1),
                        (-7, 2, -1),
                        (-6, -7, -1),
                        (-8, -7, -1),
                    ),
                )

    def test_height_filter_boundaries_and_native_limit_order(self):
        fight = SimpleNamespace(
            walkable={(-1, 0, 3), (0, 0, 4), (1, 0, 5), (0, 1, -32768)}
        )
        effect = dict(area_class="anu", area_native="circle-1")
        cells = group_cells(fight, effect, (0, 0, 99))
        self.assertEqual(cells, ((-1, 0, 3), (0, 0, 4), (1, 0, 5)))
        calls = []
        execute_ordered_group(
            decode_group_mode([2, 0, 0], raw_target_parameter=0),
            [10, 11],
            caster_id=7,
            target_id=-7,
            target_cell=(0, 0, 4),
            cell_targets=cells,
            execute_child=lambda i: calls.append(i) or True,
        )
        self.assertEqual(
            [(i.child_id, i.cell) for i in calls], [(10, (-1, 0, 3)), (10, (0, 0, 4))]
        )
        fight.walkable.add((0, 0, 9))
        with self.assertRaises(ValueError):
            group_cells(fight, effect, (0, 0, 4))

    def test_real_7320_parent_cell_groups_use_point_height_and_child_order(self):
        effects = catalog()["effects"]
        for reference in (326169, 326728):
            effect = effects[str(reference)]
            cells = group_cells(
                SimpleNamespace(walkable={(1, 0, 5), (2, 0, 8)}), effect, (1, 0, 0)
            )
            self.assertEqual(cells, ((1, 0, 5),))
            params = [
                int(effect["parameters"][i])
                for i in range(0, len(effect["parameters"]), 2)
            ]
            calls = []
            execute_ordered_group(
                decode_group_mode(params, raw_target_parameter=effect["parameters"][4]),
                effect["children"],
                caster_id=7,
                target_id=-7,
                target_cell=(1, 0, 0),
                cell_targets=cells,
                execute_child=lambda i: calls.append(i) or True,
            )
            self.assertEqual([i.child_id for i in calls], effect["children"])
            self.assertTrue(all(i.cell == (1, 0, 5) for i in calls))
