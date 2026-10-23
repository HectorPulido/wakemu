"""Observed Rushu layout uses existing native geometry, without fake terrain."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from wakfu_server.combat_rushu_scene_layout import (
    BOSS_CELL,
    GLYPH_OFFSETS,
    PLAYER_CELL,
    reconstructed_scene,
)


class RushuSceneLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = (
            Path(__file__).parent / "fixtures/ultimate_encounter_scene_recipes.json"
        )
        cls.geometry = json.loads(fixture.read_text())["maps"]["1332"]

    def without_cell(self, cell):
        geometry = deepcopy(self.geometry)
        geometry["cells"] = [row for row in geometry["cells"] if tuple(row) != cell]
        geometry["edges"] = [
            row for row in geometry["edges"] if all(tuple(p) != cell for p in row)
        ]
        return geometry

    def test_observed_relative_slots_and_boss_footprint_fit_real_native_room(self):
        before = deepcopy(self.geometry)
        scene = reconstructed_scene(self.geometry)
        self.assertEqual(self.geometry, before)
        self.assertEqual((scene["source"], scene["anchor"]), (BOSS_CELL, PLAYER_CELL))
        self.assertEqual((len(scene["cells"]), len(scene["edges"])), (431, 1602))
        native_cells = {tuple(row) for row in self.geometry["cells"]}
        native_edges = {(tuple(a), tuple(b)) for a, b in self.geometry["edges"]}
        self.assertLessEqual(scene["cells"], native_cells)
        self.assertLessEqual(scene["edges"], native_edges)
        self.assertEqual(len(scene["boss_footprint"]), 9)
        self.assertEqual(len(scene["glyph_cells"]), 16)
        self.assertEqual(len(scene["party_placement_cells"]), 15)
        self.assertEqual(
            tuple(
                (c[0] - BOSS_CELL[0], c[1] - BOSS_CELL[1]) for c in scene["glyph_cells"]
            ),
            GLYPH_OFFSETS,
        )
        self.assertTrue(all(length > 0 for length in scene["glyph_route_lengths"]))
        self.assertEqual(
            sum(length <= 12 for length in scene["glyph_route_lengths"]), 12
        )
        self.assertEqual(scene["glyph_route_lengths"][14], 6)
        self.assertFalse(scene["original_world_coordinates"])
        self.assertEqual(scene["terrain_effect_id"], 378)
        self.assertEqual(
            scene["native_border_policy"],
            "wakemu.reconstructed-native-cardinal-perimeter-v1",
        )
        border = scene["native_border_cells"]
        self.assertEqual(len(border), 96)
        self.assertLessEqual(border, scene["cells"])
        self.assertFalse(
            border
            & (
                set(scene["glyph_cells"])
                | set(scene["party_placement_cells"])
                | scene["boss_footprint"]
            )
        )
        xy = {cell[:2] for cell in scene["cells"]}
        expected = {
            cell
            for cell in scene["cells"]
            if any(
                (cell[0] + dx, cell[1] + dy) not in xy
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
        }
        self.assertEqual(border, expected)
        self.assertEqual(reconstructed_scene(self.geometry), scene)

    def test_missing_observed_glyph_cell_is_rejected_not_relocated(self):
        geometry = self.without_cell((-35, 5, -4))
        with self.assertRaisesRegex(ValueError, "required reconstructed Rushu slot"):
            reconstructed_scene(geometry)

    def test_existing_but_unreachable_glyph_is_rejected_without_new_edges(self):
        geometry = deepcopy(self.geometry)
        isolated = (-35, 5, -4)
        geometry["edges"] = [
            row for row in geometry["edges"] if tuple(row[1]) != isolated
        ]
        with self.assertRaisesRegex(ValueError, "unreachable"):
            reconstructed_scene(geometry)

    def test_incomplete_native_boss_footprint_is_rejected(self):
        geometry = self.without_cell((-50, 6, -4))
        with self.assertRaisesRegex(ValueError, "boss footprint"):
            reconstructed_scene(geometry)

    def test_wrong_map_is_not_accepted_from_matching_coordinates(self):
        geometry = dict(self.geometry, map_id=1134)
        with self.assertRaisesRegex(ValueError, "map1332"):
            reconstructed_scene(geometry)


if __name__ == "__main__":
    unittest.main()
