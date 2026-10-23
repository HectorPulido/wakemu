"""Immutable geometry reuse preserves native order and live query arguments."""
import unittest
from unittest.mock import patch

from wakfu_server import combat_area_geometry as geometry
from wakfu_server import combat_effect_targets as targets


class StaticEffectGeometryReuseTests(unittest.TestCase):
    def setUp(self):
        geometry._cached_shape_data.cache_clear()
        geometry._cached_oriented_offsets.cache_clear()
        targets._cached_isotropic_offsets.cache_clear()

    def test_native_shape_order_rotation_and_membership_match_uncached_builds(self):
        shapes = (
            ("anz", "Directed rectangle-3x4"),
            ("anC", "cone_inv-3"),
            ("anv", "cone-3"),
            ("anv", "cone--1"),
            ("anJ", "t inv-barre:2-pied:3"),
            ("anI", "t-2-3"),
            ("anG", "rectangle or square-2x4"),
            ("anG", "rectangle or square-3x3"),
            ("anF", "rectangular or square ring-w:1-2 / h:1-3"),
        )
        for kind, text in shapes:
            effect = dict(area_class=kind, area_native=text)
            raw, isotropic = geometry._build_native_area_shape(effect)
            for direction in range(8):
                for reference in ((0, 0), (-2, 1)):
                    args = dict(origin=(0, 0), reference=reference, direction=direction)
                    with self.subTest(
                        shape=text, direction=direction, reference=reference
                    ):
                        dx, dy = geometry.native_area_rotation(
                            (0, 0), reference, direction
                        )
                        expected = (
                            raw
                            if isotropic
                            else tuple(
                                dict.fromkeys(
                                    (dx * x - dy * y, dy * x + dx * y) for x, y in raw
                                )
                            )
                        )
                        self.assertEqual(
                            geometry.oriented_area_offsets(effect, **args), expected
                        )
                        for radius in (-1, 0, 1, 2):
                            for point in ((0, 0), (1, 1), (3, -1), (-2, 3)):
                                x, y = point
                                if not isotropic:
                                    x, y = dx * x + dy * y, -dy * x + dx * y
                                distance = max(0, radius)
                                member = any(
                                    (x + ox, y + oy) in frozenset(raw)
                                    for ox in range(-distance, distance + 1)
                                    for oy in range(-distance, distance + 1)
                                )
                                self.assertEqual(
                                    geometry.native_area_contains(
                                        effect, point=point, radius=radius, **args
                                    ),
                                    member,
                                )
        # Original coincident diagonal transforms are not mathematical inverses:
        # enumerating anI includes (2,-2), while its transpose membership rejects it.
        effect = dict(area_class="anI", area_native="t-0-2")
        args = dict(origin=(0, 0), reference=(0, 0), direction=0)
        self.assertIn((2, -2), geometry.oriented_area_offsets(effect, **args))
        self.assertFalse(geometry.native_area_contains(effect, point=(2, -2), **args))

    def test_repeated_membership_builds_shape_and_membership_once(self):
        effect = dict(area_class="anz", area_native="Directed rectangle-3x4", id=7)
        with patch.object(geometry, "_shape_data", wraps=geometry._shape_data) as build:
            original = geometry.native_area_shape(effect)
            for point in ((1, 0), (0, 1), (8, 8), (1, 0)):
                geometry.native_area_contains(
                    effect, origin=(0, 0), reference=(-1, 0), point=point
                )
            self.assertIs(geometry.native_area_shape(dict(effect, id=999)), original)
            self.assertEqual(build.call_count, 1)
        self.assertIsInstance(original[0], tuple)
        self.assertIsInstance(geometry._native_area_data(effect)[1], frozenset)

    def test_oriented_offsets_reuse_rotation_not_world_coordinates(self):
        effect = dict(area_class="anz", area_native="Directed rectangle-3x4")
        with patch.object(
            geometry, "_oriented_offsets", wraps=geometry._oriented_offsets
        ) as build:
            first = geometry.oriented_area_offsets(
                effect, origin=(0, 0), reference=(-1, 0)
            )
            self.assertIs(
                geometry.oriented_area_offsets(effect, origin=(9, 8), reference=(8, 8)),
                first,
            )
            other = geometry.oriented_area_offsets(
                effect, origin=(0, 0), reference=(0, -1)
            )
            self.assertNotEqual(first, other)
            self.assertEqual(build.call_count, 2)
        first_set = targets.area_offsets(effect, origin=(0, 0), reference=(-1, 0))
        self.assertIs(
            targets.area_offsets(effect, origin=(9, 8), reference=(8, 8)), first_set
        )
        self.assertEqual(first_set, frozenset(first))

    def test_mutated_ordered_points_and_same_effect_id_never_reuse_stale_geometry(self):
        effect = dict(
            id=4,
            area_class="anE",
            area_native="points",
            native_area_points=[[1, 0], [0, 1], [1, 0]],
        )
        self.assertEqual(
            geometry.native_area_shape(effect)[0], ((1, 0), (0, 1), (1, 0))
        )
        effect["native_area_points"][0][0] = 2
        self.assertEqual(
            geometry.native_area_shape(effect)[0], ((2, 0), (0, 1), (1, 0))
        )
        effect["native_area_points"].reverse()
        self.assertEqual(
            geometry.native_area_shape(effect)[0], ((1, 0), (0, 1), (2, 0))
        )
        effect["native_area_points"][0][0] = True
        with self.assertRaisesRegex(ValueError, "ordered point"):
            geometry.native_area_shape(effect)

    def test_facing_origin_radius_and_validation_remain_live(self):
        effect = dict(area_class="anI", area_native="t-1-2")
        geometry.native_area_shape(effect)
        self.assertNotEqual(
            geometry.oriented_area_offsets(
                effect, origin=(0, 0), reference=(0, 0), direction=0
            ),
            geometry.oriented_area_offsets(
                effect, origin=(0, 0), reference=(0, 0), direction=1
            ),
        )
        with self.assertRaisesRegex(ValueError, "authoritative actor facing"):
            geometry.oriented_area_offsets(effect, origin=(0, 0), reference=(0, 0))
        for radius in (True, 128, -129):
            with self.subTest(radius=radius), self.assertRaisesRegex(
                ValueError, "signed-byte"
            ):
                geometry.native_area_contains(
                    effect,
                    origin=(0, 0),
                    reference=(-1, 0),
                    point=(0, 0),
                    radius=radius,
                )
        for text in ("Directed rectangle-2x3", "Directed rectangle-1x0"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                geometry.native_area_shape(dict(area_class="anz", area_native=text))
        # Cache limits do not become new gameplay limits.
        big = dict(area_class="anv", area_native="cone-33")
        before = geometry._cached_shape_data.cache_info()
        self.assertEqual(len(geometry.native_area_shape(big)[0]), 33**2)
        self.assertEqual(geometry._cached_shape_data.cache_info(), before)

    def test_isotropic_shapes_reuse_only_complete_content_and_stay_immutable(self):
        cases = (
            ("anD", "point"),
            ("anA", "empty"),
            ("anu", "circle-3"),
            ("anH", "ring-3-1"),
            ("any", "crossRing-1-3"),
            ("anw", "cross-h2b1-g-1d3"),
            ("anx", "crossDiag-h2b0-g1d-2"),
        )
        with patch.object(
            targets, "_isotropic_offsets", wraps=targets._isotropic_offsets
        ) as build:
            for kind, text in cases:
                effect = dict(id=10, area_class=kind, area_native=text)
                first = targets.area_offsets(effect)
                self.assertIsInstance(first, frozenset)
                self.assertIs(targets.area_offsets(dict(effect, id=20)), first)
                self.assertEqual(first, targets._isotropic_offsets(kind, text))
            self.assertEqual(build.call_count, 2 * len(cases))
        effect = dict(id=10, area_class="anu", area_native="circle-1")
        first = targets.area_offsets(effect)
        effect["area_native"] = "circle-2"
        self.assertGreater(len(targets.area_offsets(effect)), len(first))
        with self.assertRaises(targets.UnsupportedEffectArea):
            targets.area_offsets(dict(area_class="anu", area_native="unknown"))
