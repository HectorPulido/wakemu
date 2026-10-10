"""Duel actors retain their positions beyond the compact NPC encounter cap."""
import unittest
from unittest.mock import patch
from wakfu_server.combat_terrain import local_arena


class DuelArenaRadiusTests(unittest.TestCase):
    def test_duel_separation_above_twelve_uses_configured_native_topology(self):
        cells = [(x, 0, 0) for x in range(21)]
        edges = [(a, b) for a, b in zip(cells, cells[1:])]
        edges += [(b, a) for a, b in edges]
        geometry = dict(map_id=9001, cells=cells, edges=edges)
        with patch.dict("os.environ", {"WAKFU_COMBAT_ARENA_RADIUS": "89"}), patch(
            "wakfu_server.combat_terrain.published_geometry", return_value=geometry
        ), patch(
            "wakfu_server.combat_terrain.native_qi_surfaces", return_value=object()
        ), patch(
            "wakfu_server.combat_terrain.native_surface_indices",
            side_effect=lambda surface, selected: {cell[:2]: 0 for cell in selected},
        ), patch(
            "wakfu_server.combat_terrain.native_qi_surface_provenance",
            return_value=dict(map_id=9001),
        ):
            duel = local_arena(9001, 7, cells[0], cells[-1], relocate_monsters=False)
            encounter = local_arena(9001, 8, cells[0], cells[-1])
        self.assertIn(cells[-1], duel["validated_cells"])
        self.assertIn(cells[-1], duel["placement_cells"][1])
        self.assertEqual(duel["participant_positions"], [])
        self.assertIn(cells[-1], encounter["validated_cells"])
        self.assertLessEqual(len(encounter["validated_cells"]), 4900)
