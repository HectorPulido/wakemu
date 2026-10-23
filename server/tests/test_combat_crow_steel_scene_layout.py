"""Aerial scene policies retain exported terrain and disconnected platforms."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from wakfu_server.combat_crow_steel_scene_layout import (
    CROW_BOSS,
    STEEL_BOSSES,
    reconstructed_crow_scene,
    reconstructed_steel_scene,
)
from wakfu_server.combat_geometry import prepare_geometry, reachable


class CrowSteelSceneLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = (
            Path(__file__).parent / "fixtures/ultimate_encounter_scene_recipes.json"
        )
        cls.maps = json.loads(fixture.read_text())["maps"]

    def assert_native_scene(self, map_id, provider, **kwargs):
        geometry = self.maps[str(map_id)]
        before = deepcopy(geometry)
        scene = provider(geometry, **kwargs)
        self.assertEqual(geometry, before)
        native = prepare_geometry(geometry)
        self.assertLessEqual(scene["cells"], native.cells)
        self.assertLessEqual(scene["edges"], native.edges)
        self.assertEqual(len(scene["boss_footprint"]), 9)
        self.assertFalse(scene["original_world_coordinates"])
        self.assertEqual(len(scene["party_placement_cells"]), 6)
        party = scene["party_placement_cells"]
        self.assertEqual(party[0], scene["anchor"])
        for index, cell in enumerate(party):
            self.assertIn(cell, scene["main_board_cells"])
            for other in party[index + 1 :]:
                self.assertGreaterEqual(
                    abs(cell[0] - other[0]) + abs(cell[1] - other[1]), 3
                )
        reached = reachable(scene["anchor"], scene["cells"], native.outgoing)
        self.assertLessEqual(set(party), reached)
        self.assertFalse(reached & scene["aerial_platform_cells"])
        self.assertEqual(provider(geometry, **kwargs), scene)
        return scene

    def test_crow_keeps_native_aerial_platform_and_excludes_duplicate_map_copy(self):
        scene = self.assert_native_scene(363, reconstructed_crow_scene)
        self.assertEqual(scene["source"], CROW_BOSS)
        self.assertEqual(len(scene["cells"]), 196)
        self.assertEqual(len(scene["main_board_cells"]), 187)
        self.assertTrue(all(cell[1] > -200 for cell in scene["cells"]))
        self.assertEqual(scene["native_initial_glyphs"][0]["reference"], 1724)
        landing = tuple(scene["native_initial_glyphs"][0]["cell"])
        self.assertEqual(landing, (-5, -4, 88))
        footprint = {
            (landing[0] + dx, landing[1] + dy, landing[2])
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
        }
        self.assertLessEqual(footprint, scene["main_board_cells"])
        self.assertFalse(footprint & set(scene["party_placement_cells"]))

    def test_steel_both_initial_sides_keep_the_same_native_arena(self):
        left = self.assert_native_scene(959, reconstructed_steel_scene)
        right = self.assert_native_scene(959, reconstructed_steel_scene, side="right")
        self.assertEqual(
            (left["source"], right["source"]), tuple(STEEL_BOSSES.values())
        )
        self.assertEqual(left["cells"], right["cells"])
        self.assertEqual(left["edges"], right["edges"])
        self.assertEqual(
            (len(left["cells"]), len(left["aerial_platform_cells"])), (306, 18)
        )
        self.assertEqual(
            (left["terrain_effect_id"], right["terrain_effect_id"]), (909, 909)
        )
        from wakfu_server.combat_arena_selection import cardinal_border_cells

        self.assertEqual(left["native_border_scope_cells"], left["main_board_cells"])
        self.assertEqual(
            left["native_border_cells"], cardinal_border_cells(left["main_board_cells"])
        )
        self.assertEqual(len(left["native_border_cells"]), 104)
        self.assertFalse(left["native_border_cells"] & left["aerial_platform_cells"])
        self.assertFalse(
            left["native_border_cells"] & set(left["party_placement_cells"])
        )
        from wakfu_server.combat_area_geometry import oriented_area_offsets

        # Installed native-point-areas152475/152479, respectively. The
        # producer's directional transform must land on the other real island.
        for scene, points, opposite in (
            (left, [[16, -16]], right["source"]),
            (right, [[16, 16]], left["source"]),
        ):
            effect = dict(
                area_class="anE",
                area_native="forme à base de points",
                native_area_points=points,
            )
            (offset,) = oriented_area_offsets(
                effect,
                origin=scene["source"],
                reference=scene["source"],
                direction=scene["boss_direction"],
            )
            destination = (
                scene["source"][0] + offset[0],
                scene["source"][1] + offset[1],
                scene["source"][2],
            )
            self.assertEqual(destination, opposite)
            self.assertIn(destination, scene["aerial_platform_cells"])

    def test_missing_native_platform_cell_is_rejected_without_fabrication(self):
        geometry = deepcopy(self.maps["363"])
        missing = (-7, -18, 88)
        geometry["cells"] = [c for c in geometry["cells"] if tuple(c) != missing]
        geometry["edges"] = [
            e for e in geometry["edges"] if all(tuple(c) != missing for c in e)
        ]
        with self.assertRaisesRegex(ValueError, "complete aerial boss footprints"):
            reconstructed_crow_scene(geometry)

    def test_existing_island_with_broken_native_connectivity_is_rejected(self):
        geometry = deepcopy(self.maps["959"])
        geometry["edges"] = [
            e for e in geometry["edges"] if tuple(e[1]) != STEEL_BOSSES["left"]
        ]
        with self.assertRaisesRegex(ValueError, "not mutually reachable"):
            reconstructed_steel_scene(geometry)

    def test_wrong_map_and_unrecognized_side_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "map363"):
            reconstructed_crow_scene(self.maps["959"])
        with self.assertRaisesRegex(ValueError, "left or right"):
            reconstructed_steel_scene(self.maps["959"], side="nearby")


if __name__ == "__main__":
    unittest.main()
