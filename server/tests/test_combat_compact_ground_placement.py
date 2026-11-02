"""Ordinary compact placements keep source ground separate from raw terrain."""
import unittest
from wakfu_server.combat_arena_selection import compact_encounter, prepare_geometry
from wakfu_server.combat_placement_footprints import covered_cells


class CompactGroundPlacementTests(unittest.TestCase):
    def setUp(self):
        cells = {(x, y, 0) for x in range(9) for y in range(9)}
        edges = {
            (a, b)
            for a in cells
            for b in cells
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        }
        self.geometry = prepare_geometry(dict(map_id=1, cells=cells, edges=edges))
        self.options = dict(
            minimum_dimensions=(9, 9), player_slots=6, allow_border_footprints=True
        )

    def test_unsupported_center_is_excluded_without_removing_native_terrain(self):
        hole = (4, 4, 0)
        ground = self.geometry.cells - {hole}
        result = compact_encounter(
            self.geometry,
            (1, 1, 0),
            [hole],
            placement_ground_cells=ground,
            **self.options
        )
        self.assertIn(hole, result["cells"])
        self.assertTrue(any(hole in edge for edge in result["edges"]))
        self.assertNotEqual(result["participant_positions"][0][1], hole)
        self.assertTrue(
            all(
                cell in ground for team in result["placement"].values() for cell in team
            )
        )

    def test_positive_body_can_overhang_unsupported_native_column(self):
        center, hole = (4, 4, 0), (5, 4, 0)
        result = compact_encounter(
            self.geometry,
            (1, 1, 0),
            [center],
            member_radii=(1,),
            placement_ground_cells=self.geometry.cells - {hole},
            **self.options
        )
        self.assertEqual(result["participant_positions"][0][1], center)
        self.assertIn(hole, covered_cells(center, 1, result["cells"]))

    def test_changed_ground_mask_does_not_reuse_an_ineligible_cached_center(self):
        center = (4, 4, 0)
        first = compact_encounter(
            self.geometry,
            (1, 1, 0),
            [center],
            placement_ground_cells=self.geometry.cells,
            **self.options
        )
        changed = compact_encounter(
            self.geometry,
            (1, 1, 0),
            [center],
            placement_ground_cells=self.geometry.cells - {center},
            **self.options
        )
        self.assertEqual(first["participant_positions"][0][1], center)
        self.assertNotEqual(changed["participant_positions"][0][1], center)


if __name__ == "__main__":
    unittest.main()
