import unittest
from wakfu_server.combat_area_geometry import (
    native_area_shape,
    oriented_area_offsets,
    native_area_contains,
)


class InverseConeAreaTests(unittest.TestCase):
    def test_native_ordered_rows_and_empty_boundary(self):
        effect = {"area_class": "anC", "area_native": "cone_inv-3"}
        self.assertEqual(
            native_area_shape(effect),
            (
                (
                    (2, 0),
                    (1, -1),
                    (1, 0),
                    (1, 1),
                    (0, -2),
                    (0, -1),
                    (0, 0),
                    (0, 1),
                    (0, 2),
                ),
                False,
            ),
        )
        for height in (-1, 0):
            self.assertEqual(
                native_area_shape(dict(effect, area_native="cone_inv-" + str(height))),
                ((), False),
            )

    def test_shared_orientation_and_physical_radius_preserve_inverse_footprint(self):
        effect = {"area_class": "anC", "area_native": "cone_inv-3"}
        offsets = oriented_area_offsets(effect, origin=(0, 0), reference=(-1, 0))
        self.assertEqual(
            offsets,
            ((2, 0), (1, -1), (1, 0), (1, 1), (0, -2), (0, -1), (0, 0), (0, 1), (0, 2)),
        )
        self.assertTrue(
            native_area_contains(effect, origin=(0, 0), reference=(-1, 0), point=(0, 2))
        )
        self.assertFalse(
            native_area_contains(effect, origin=(0, 0), reference=(-1, 0), point=(2, 2))
        )
        self.assertTrue(
            native_area_contains(
                effect, origin=(0, 0), reference=(-1, 0), point=(2, 2), radius=1
            )
        )
