import unittest
from wakfu_server.combat_condition_distance import (
    DistanceActor,
    native_caster_target_distance,
)


class NativeCriterionDistanceTests(unittest.TestCase):
    def test_zero_radius_normal_and_diagonal(self):
        caster = DistanceActor(0, 0, 0)
        self.assertEqual(
            native_caster_target_distance(caster, DistanceActor(3, 0, 0)), 3
        )
        self.assertEqual(
            native_caster_target_distance(caster, DistanceActor(3, 3, 0)), 6
        )

    def test_radius_clamps_each_axis_before_adding(self):
        caster = DistanceActor(0, 0, 1)
        self.assertEqual(
            native_caster_target_distance(caster, DistanceActor(3, 3, 1)), 2
        )
        self.assertEqual(
            native_caster_target_distance(caster, DistanceActor(1, 4, 1)), 2
        )
        self.assertEqual(
            native_caster_target_distance(caster, DistanceActor(1, 1, 1)), 0
        )

    def test_cell_has_only_caster_radius_and_ignores_height(self):
        caster = DistanceActor(0, 0, 1)
        self.assertEqual(native_caster_target_distance(caster, (3, 3, 999)), 4)
        self.assertEqual(native_caster_target_distance(caster, (3, 3, -99)), 4)

    def test_actual_absent_target_or_caster_returns_native_minus_one(self):
        self.assertEqual(
            native_caster_target_distance(DistanceActor(0, 0, 0), None), -1
        )
        self.assertEqual(native_caster_target_distance(None, (0, 0, 0)), -1)

    def test_missing_radius_is_never_assumed_zero(self):
        with self.assertRaises(ValueError):
            DistanceActor(0, 0, None)
