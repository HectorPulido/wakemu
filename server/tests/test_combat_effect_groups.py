import unittest
from wakfu_server.combat_effect_groups import (
    decode_group_mode,
    execute_ordered_group,
    UnsupportedEffectGroup,
)


class NativeEffectGroupTests(unittest.TestCase):
    def run_group(self, parameters, callback, **overrides):
        mode = decode_group_mode(
            parameters,
            raw_target_parameter=parameters[2] if len(parameters) >= 3 else None,
        )
        args = dict(
            caster_id=10, target_id=20, target_cell=(1, 2, 0), execute_child=callback
        )
        args.update(overrides)
        return execute_ordered_group(mode, (101, 102, 103), **args)

    def test_default_target_and_order(self):
        calls = self.run_group((), lambda call: True)
        self.assertEqual([c.child_id for c in calls], [101, 102, 103])
        self.assertTrue(all(c.caster_id == 10 and c.target_id == 20 for c in calls))

    def test_limit_counts_attempts_or_successes(self):
        calls = self.run_group((1, 0), lambda call: call.child_id == 102)
        self.assertEqual([c.child_id for c in calls], [101])
        calls = self.run_group((1, 1), lambda call: call.child_id == 102)
        self.assertEqual([c.child_id for c in calls], [101, 102])

    def test_cell_expands_parent_area_per_child(self):
        calls = self.run_group(
            (3, 0, 0), lambda call: True, cell_targets=((1, 2, 0), (2, 2, 0))
        )
        self.assertEqual(
            [(c.child_id, c.cell) for c in calls],
            [(101, (1, 2, 0)), (101, (2, 2, 0)), (102, (1, 2, 0))],
        )
        self.assertTrue(all(c.target_id is None for c in calls))

    def test_rebinding_and_transmission(self):
        calls = self.run_group((0, 0, 1, 0, 1, 1), lambda call: True)
        self.assertEqual((calls[0].caster_id, calls[0].target_id), (20, 20))
        calls = self.run_group(
            (0, 0, 1, 0, 1, 2), lambda call: True, caster_cell=(4, 5, 0)
        )
        self.assertEqual((calls[0].caster_id, calls[0].target_id), (20, 10))
        self.assertEqual(calls[0].cell, (4, 5, 0))
        calls = self.run_group((0, 0, 1, 0, 0), lambda call: True)
        self.assertIsNone(calls[0].target_id)

    def test_target_mode_uses_raw_parameter_not_level_evaluated(self):
        self.assertTrue(decode_group_mode((0, 0, 0), raw_target_parameter=1).on_target)
        self.assertFalse(
            decode_group_mode((0, 0, 10), raw_target_parameter=10).on_target
        )
        with self.assertRaises(UnsupportedEffectGroup):
            decode_group_mode((0, 0, 0))

    def test_relative_and_missing_area_are_unknown(self):
        with self.assertRaises(UnsupportedEffectGroup):
            self.run_group((0, 0, 1, 1), lambda call: True)
        with self.assertRaises(UnsupportedEffectGroup):
            self.run_group((0, 0, 0), lambda call: True)
