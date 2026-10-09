import unittest
from wakfu_server.combat_portal_casting import (
    evaluate_portal_casting,
    portal_exit_distance,
)


class PortalCastingTests(unittest.TestCase):
    def gate(self, uid, cell, affiliation=0):
        return dict(
            uid=uid, cell=cell, native_type_id=19, native_fight_affiliation=affiliation
        )

    def evaluate(self, areas, **changes):
        options = dict(
            caster_cell=(0, 0, 0),
            caster_affiliation=0,
            target_cell=(10, 0, 0),
            minimum=0,
            maximum=2,
            same_cell_category=False,
            cell_occupants=lambda x, y: frozenset(),
            los_required=lambda: False,
            linear_required=lambda target: False,
            visible=lambda source, target: True,
        )
        options.update(changes)
        return evaluate_portal_casting(areas, **options)

    def test_single_entry_is_excluded_from_exits(self):
        one = self.evaluate([self.gate(1, (1, 0, 0))])
        self.assertTrue(one.has_entry)
        self.assertFalse(one.range_accepts)
        self.assertEqual(dict(one.exit_failures), {})
        two = self.evaluate([self.gate(1, (1, 0, 0)), self.gate(2, (9, 0, 0))])
        self.assertEqual(two.entry_uids, frozenset([1]))
        self.assertEqual(two.exit_failures[2], frozenset())
        self.assertTrue(two.range_accepts and two.alignment_accepts and two.los_accepts)

    def test_multiple_entries_are_also_exits(self):
        result = self.evaluate(
            [self.gate(1, (1, 0, 0)), self.gate(2, (2, 0, 0))], target_cell=(1, 0, 0)
        )
        self.assertEqual(result.entry_uids, frozenset([1, 2]))
        self.assertEqual(set(result.exit_failures), {1, 2})
        self.assertTrue(result.los_accepts)
        with self.assertRaises(TypeError):
            result.exit_failures[1] = frozenset(["twI"])

    def test_all_three_failure_channels_remain_independent(self):
        gates = [self.gate(1, (1, 0, 0)), self.gate(2, (9, 2, 0))]
        result = self.evaluate(
            gates,
            linear_required=lambda target: True,
            los_required=lambda: True,
            visible=lambda source, target: source == (0, 0, 0),
        )
        self.assertEqual(result.exit_failures[2], frozenset(["twU", "twI", "twG"]))
        self.assertFalse(
            result.range_accepts or result.alignment_accepts or result.los_accepts
        )
        result = self.evaluate(gates, maximum=4, linear_required=lambda target: True)
        self.assertTrue(result.range_accepts)
        self.assertFalse(result.alignment_accepts)
        self.assertFalse(result.los_accepts)

    def test_same_cell_category_skips_exit_los_and_line_checks(self):
        calls = []
        result = self.evaluate(
            [self.gate(1, (1, 0, 0)), self.gate(2, (10, 0, 9))],
            same_cell_category=True,
            linear_required=lambda target: calls.append(target) or False,
        )
        self.assertEqual(result.exit_failures[2], frozenset())
        self.assertEqual(calls, [(1, 0, 0)])
        result = self.evaluate(
            [self.gate(1, (1, 0, 0)), self.gate(2, (10, 1, 0))], same_cell_category=True
        )
        self.assertEqual(result.exit_failures[2], frozenset(["twI"]))

    def test_affiliation_and_actual_qi_occupancy_filter_all_portals(self):
        gates = [
            self.gate(1, (1, 0, 0)),
            self.gate(2, (9, 0, 0)),
            self.gate(3, (10, 0, 0), affiliation=1),
        ]
        result = self.evaluate(
            gates, cell_occupants=lambda x, y: frozenset([7]) if x == 9 else frozenset()
        )
        self.assertEqual(result.entry_uids, frozenset([1]))
        self.assertEqual(dict(result.exit_failures), {})

    def test_entry_conditional_linear_uses_gate_cell_exit_uses_target(self):
        calls = []
        self.evaluate(
            [self.gate(1, (1, 0, 0)), self.gate(2, (9, 0, 0))],
            linear_required=lambda target: calls.append(target) or False,
        )
        self.assertEqual(calls, [(1, 0, 0), (10, 0, 0)])

    def test_java_overflow_distances_and_no_negative_maximum_shortcut(self):
        self.assertEqual(
            portal_exit_distance((0, 0, 0), (-(1 << 31), 0, 0)), -(1 << 31)
        )
        result = self.evaluate(
            [self.gate(1, (0, 0, 0)), self.gate(2, (-(1 << 31), 0, 0))],
            target_cell=(0, 0, 0),
            same_cell_category=True,
        )
        self.assertEqual(result.entry_uids, frozenset([1, 2]))
        self.assertTrue(result.los_accepts)
        self.assertFalse(self.evaluate([self.gate(1, (1, 0, 0))], maximum=-1).has_entry)

    def test_missing_authority_stays_unknown(self):
        gate = self.gate(1, (1, 0, 0))
        for changes in (
            dict(cell_occupants=lambda x, y: None),
            dict(los_required=lambda: None),
            dict(linear_required=lambda target: 0),
            dict(visible=lambda source, target: None, los_required=lambda: True),
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.evaluate([gate], **changes)


if __name__ == "__main__":
    unittest.main()
