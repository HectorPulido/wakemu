import unittest
from types import SimpleNamespace
from wakfu_server.combat_area_geometry import native_area_shape, native_area_contains
from wakfu_server.combat_effect_targets import select_effect_targets


class NativeRectangleRingTests(unittest.TestCase):
    def test_original_quadrant_order_and_center_boundary(self):
        effect = {
            "area_class": "anF",
            "area_native": "rectangular or square ring-w:1-1 / h:1-1",
        }
        expected = (
            (0, 1),
            (0, -1),
            (1, 0),
            (-1, 0),
            (1, 1),
            (-1, 1),
            (1, -1),
            (-1, -1),
        )
        self.assertEqual(native_area_shape(effect), (expected, False))
        for x in range(-2, 3):
            for y in range(-2, 3):
                self.assertEqual(
                    native_area_contains(
                        effect, origin=(0, 0), reference=(-1, 0), point=(x, y)
                    ),
                    (x, y) in expected,
                )

    def test_multiple_targets_caster_and_height_independence(self):
        effect = {
            "area_class": "anF",
            "area_native": "rectangular or square ring-w:1-1 / h:1-1",
        }
        caster = SimpleNamespace(id=1, position=(0, 0, 7), direction=1, team=0, hp=50)
        actors = [caster] + [
            SimpleNamespace(id=i, position=p, team=1, hp=50)
            for i, p in enumerate([(1, 0, 2), (1, 1, -2), (0, 0, 0), (2, 0, 0)], 2)
        ]
        before = [a.position for a in actors]
        self.assertEqual(
            [
                a.id
                for a in select_effect_targets(
                    effect, caster, (0, 0, 7), actors, relations={"self", "enemy"}
                )
            ],
            [2, 3],
        )
        self.assertEqual(before, [a.position for a in actors])

    def test_rectangular_hole_uses_both_axes_and_zero_includes_center(self):
        effect = {
            "area_class": "anF",
            "area_native": "rectangular or square ring-w:1-2 / h:2-3",
        }
        points, _ = native_area_shape(effect)
        self.assertNotIn((0, 1), points)
        self.assertIn((1, 1), points)
        self.assertIn((0, 2), points)
        self.assertNotIn((3, 0), points)
        self.assertEqual(
            native_area_shape(
                dict(effect, area_native="rectangular or square ring-w:0-0 / h:0-0")
            ),
            (((0, 0),), False),
        )
