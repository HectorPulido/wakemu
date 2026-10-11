"""anz.bEx ordering and anc directional routing, without catalog dependencies."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat.combat_area_geometry import (
    native_area_shape,
    native_area_contains,
)
from wakfu_server.combat.combat_effect_targets import (
    area_offsets,
    UnsupportedEffectArea,
)
from wakfu_server.combat.combat_group_cells import ordered_offsets, group_cells


class DirectedRectangleTests(unittest.TestCase):
    def effect(self, width=1, length=5):
        return dict(
            area_class="anz", area_native=f"Directed rectangle-{width}x{length}"
        )

    def test_native_width_is_full_odd_width_and_order_is_y_major(self):
        self.assertEqual(
            native_area_shape(self.effect(3, 2)),
            (
                ((0, -1), (1, -1), (0, 0), (1, 0), (0, 1), (1, 1)),
                False,
            ),
        )
        for length in (2, 5, 6):
            self.assertEqual(
                native_area_shape(self.effect(1, length))[0],
                tuple((x, 0) for x in range(length)),
            )

    def test_existing_anc_rotation_drives_ordered_cells(self):
        effect = self.effect(1, 3)
        self.assertEqual(
            ordered_offsets(effect, origin=(0, 2), reference=(0, 0)),
            ((0, 0), (0, 1), (0, 2)),
        )
        caster = SimpleNamespace(id=1, position=(0, 0, 0), direction=1)
        fight = SimpleNamespace(actors={1: caster}, walkable={(0, 2, 4), (0, 3, 5)})
        self.assertEqual(
            group_cells(fight, effect, (0, 2, 0), caster_id=1), ((0, 2, 4), (0, 3, 5))
        )

    def test_membership_uses_direction_and_forward_length(self):
        effect = self.effect(1, 3)
        for point in ((0, 2), (0, 3), (0, 4)):
            self.assertTrue(
                native_area_contains(
                    effect, origin=(0, 2), reference=(0, 0), point=point
                )
            )
        for point in ((0, 1), (1, 2), (0, 5)):
            self.assertFalse(
                native_area_contains(
                    effect, origin=(0, 2), reference=(0, 0), point=point
                )
            )

    def test_missing_orientation_and_impossible_dimensions_fail_closed(self):
        with self.assertRaises(UnsupportedEffectArea):
            area_offsets(self.effect())
        for width, length in ((0, 2), (2, 2), (1, 0), (1, 1 << 31)):
            with self.subTest(width=width, length=length), self.assertRaises(
                ValueError
            ):
                native_area_shape(self.effect(width, length))


if __name__ == "__main__":
    unittest.main()
