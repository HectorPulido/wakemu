"""Aura reuse retains live authority and mutable-checkpoint invalidation."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_effect_area_geometry as geometry


class EffectAreaGeometryReuseTests(unittest.TestCase):
    def setUp(self):
        geometry._aura_cells.cache_clear()
        geometry._footprint_membership.cache_clear()
        self.owner = SimpleNamespace(position=(0, 0, 0))
        self.fight = SimpleNamespace(actors={7: self.owner})
        self.row = dict(
            uid=91,
            reference=1527,
            owner_id=7,
            native_area_contract="faN",
            native_anchor_id=7,
            native_anchor_source="faN.bgZ",
            direction=0,
            child_effect_uids={8: [32]},
        )
        self.definition = dict(
            type="AURA", native_shape_class="anu", native_shape_description="circle-1"
        )
        self.definitions = {"1527": self.definition}
        self.catalog = patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=self.definitions,
        )
        self.catalog.start()
        self.addCleanup(self.catalog.stop)

    def test_repeated_queries_generate_once_but_follow_live_position(self):
        with patch.object(
            geometry, "registered_area_cells", wraps=geometry.registered_area_cells
        ) as generate:
            for _ in range(12):
                geometry.refresh_area_geometry(self.fight, self.row)
                self.assertTrue(geometry.contains_area_cell(self.row, (1, 0, 99)))
            self.assertEqual(generate.call_count, 1)
            self.owner.position = (5, 5, 2)
            geometry.refresh_area_geometry(self.fight, self.row)
            self.assertEqual(generate.call_count, 2)
            self.assertEqual(self.row["cell"], (5, 5, 2))
            self.assertFalse(geometry.contains_area_cell(self.row, (1, 0, 0)))
            self.assertTrue(geometry.contains_area_cell(self.row, (6, 5, -9)))
            self.assertEqual(self.row["child_effect_uids"], {8: [32]})

    def test_direction_prototype_reference_and_point_edits_invalidate(self):
        self.definition.update(
            native_shape_class="anE",
            native_shape_description="forme à base de points",
            native_area_points=[[1, 0], [0, 1]],
        )
        with patch.object(
            geometry, "registered_area_cells", wraps=geometry.registered_area_cells
        ) as generate:
            geometry.refresh_area_geometry(self.fight, self.row)
            original = self.row["native_cells_xy"]
            self.row["direction"] = 7
            geometry.refresh_area_geometry(self.fight, self.row)
            self.assertNotEqual(self.row["native_cells_xy"], original)
            self.definition["native_area_points"][0][0] = 3
            geometry.refresh_area_geometry(self.fight, self.row)
            self.assertEqual(
                self.row["native_cells_xy"],
                geometry.registered_area_cells(self.definition, self.owner.position, 7),
            )
            self.definitions["1528"] = dict(self.definition)
            self.row["reference"] = 1528
            geometry.refresh_area_geometry(self.fight, self.row)
            self.definitions["1528"][
                "native_shape_description"
            ] = "different description"
            geometry.refresh_area_geometry(self.fight, self.row)
            # Five actual refresh inputs, plus the explicit expected-value call.
            self.assertEqual(generate.call_count, 6)

    def test_warm_geometry_does_not_bypass_live_authority_or_validation(self):
        geometry.refresh_area_geometry(self.fight, self.row)
        bad_rows = [
            dict(self.row, native_anchor_id=8),
            dict(self.row, native_anchor_source="forged"),
            dict(self.row, owner_id=8),
        ]
        for row in bad_rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                geometry.refresh_area_geometry(self.fight, row)
        self.fight.actors.clear()
        with self.assertRaisesRegex(ValueError, "owner PV"):
            geometry.refresh_area_geometry(self.fight, self.row)
        self.fight.actors[7] = self.owner
        self.owner.position = (False, 0, 0)
        with self.assertRaisesRegex(ValueError, "coordinates"):
            geometry.refresh_area_geometry(self.fight, self.row)
        self.owner.position = (0, 0, 0)
        self.definition["type"] = "GLYPH"
        with self.assertRaisesRegex(ValueError, "AURA prototype"):
            geometry.refresh_area_geometry(self.fight, self.row)
        self.definition["type"] = "AURA"
        self.definition["native_shape_description"] = "unrecognized geometry"
        with self.assertRaises(ValueError):
            geometry.refresh_area_geometry(self.fight, self.row)

    def test_clone_and_source_identity_are_not_cached_as_mutable_objects(self):
        geometry.refresh_area_geometry(self.fight, self.row)
        clone = deepcopy(self.fight)
        clone_row = deepcopy(self.row)
        geometry.refresh_area_geometry(clone, clone_row)
        original_cells = self.row["native_cells_xy"]
        clone.actors[7].position = (9, 8, 7)
        geometry.refresh_area_geometry(clone, clone_row)
        self.assertEqual(self.row["native_cells_xy"], original_cells)
        self.assertEqual(self.row["cell"], (0, 0, 0))
        self.assertEqual(clone_row["cell"], (9, 8, 7))
        clone_row["child_effect_uids"][8].append(99)
        self.assertEqual(self.row["child_effect_uids"], {8: [32]})
        self.assertEqual(self.row["uid"], clone_row["uid"])
        self.assertEqual(
            set(self.row) - {"native_cells_xy", "cell"},
            {
                "uid",
                "reference",
                "owner_id",
                "native_area_contract",
                "native_anchor_id",
                "native_anchor_source",
                "direction",
                "child_effect_uids",
            },
        )
        json.dumps(self.row)

    def test_membership_reuses_immutable_set_and_observes_checkpoint_edits(self):
        row = dict(native_cells_xy=[[1, 2], [3, 4]])
        for _ in range(8):
            self.assertTrue(geometry.contains_area_cell(row, (1, 2, 999)))
        self.assertEqual(geometry._footprint_membership.cache_info().misses, 1)
        row["native_cells_xy"][0][0] = 8
        self.assertFalse(geometry.contains_area_cell(row, (1, 2, 0)))
        self.assertTrue(geometry.contains_area_cell(row, (8, 2, 0)))
        row["native_cells_xy"] = ((7, 6),)
        self.assertTrue(geometry.contains_area_cell(row, (7, 6, -1)))
        self.assertFalse(geometry.contains_area_cell(row, (8, 2, 0)))
        self.assertEqual(set(row), {"native_cells_xy"})
        self.assertEqual(geometry._footprint_membership.cache_info().maxsize, 2048)

    def test_physical_radius_matches_native_square_expansion_with_one_lookup(self):
        row = dict(native_cells_xy=((1, 2), (5, 4), (-3, 1)))
        footprint = set(row["native_cells_xy"])
        for radius in (-2, -1, 0, 1, 2, 3):
            for x in range(-5, 7):
                for y in range(-3, 7):
                    expected = (x, y) in footprint or any(
                        (x + dx, y + dy) in footprint
                        for dx in range(-radius, radius + 1)
                        for dy in range(-radius, radius + 1)
                    )
                    self.assertEqual(
                        geometry.contains_area_actor(row, (x, y, 99), radius), expected
                    )
        with patch.object(
            geometry, "_area_membership", wraps=geometry._area_membership
        ) as membership:
            self.assertFalse(geometry.contains_area_actor(row, (30, 30, 0), 5))
            self.assertEqual(membership.call_count, 1)
        for invalid in (True, -129, 128, 1.5):
            with self.subTest(radius=invalid), self.assertRaises(ValueError):
                geometry.contains_area_actor(row, (0, 0, 0), invalid)

    def test_hour_fallback_and_missing_footprint_keep_the_existing_contract(self):
        row = dict(native_hour_contract=True, cell=[5, 6, 7])
        self.assertTrue(geometry.contains_area_cell(row, (5, 6, -9)))
        row["cell"][0] = 9
        self.assertFalse(geometry.contains_area_cell(row, (5, 6, 7)))
        self.assertTrue(geometry.contains_area_cell(row, (9, 6, 7)))
        self.assertFalse(geometry.contains_area_cell({}, None))
        with self.assertRaises(ValueError):
            geometry.contains_area_cell({}, (0, 0, 0))
        untouched = {"native_area_contract": "faG"}
        self.assertIs(geometry.refresh_area_geometry(self.fight, untouched), untouched)

    def test_large_geometry_remains_usable_without_retained_cache_populations(self):
        self.definition["native_shape_description"] = "circle-33"
        with patch.object(
            geometry, "registered_area_cells", wraps=geometry.registered_area_cells
        ) as generate:
            for _ in range(2):
                geometry.refresh_area_geometry(self.fight, self.row)
                self.assertTrue(geometry.contains_area_cell(self.row, (33, 0, 0)))
            self.assertEqual(generate.call_count, 2)
            self.assertEqual(geometry._aura_cells.cache_info().currsize, 0)
        row = dict(native_cells_xy=tuple((x, 0) for x in range(4097)))
        before = geometry._footprint_membership.cache_info()
        self.assertTrue(geometry.contains_area_cell(row, (4096, 0, 0)))
        self.assertEqual(geometry._footprint_membership.cache_info(), before)


if __name__ == "__main__":
    unittest.main()
