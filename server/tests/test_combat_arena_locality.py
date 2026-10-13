"""Relocated fights stay on nearby native ground around long obstacles."""
import unittest

from wakfu_server.combat_arena_selection import compact_encounter
from wakfu_server.combat_geometry import prepare_geometry, reachable


class CombatArenaLocalityTests(unittest.TestCase):
    def test_narrow_walkway_does_not_expand_across_long_detour(self):
        cells = {(x, y, 0) for x in range(30) for y in range(3)}
        cells |= {(x, y, 0) for x in range(30) for y in range(5, 16)}
        cells |= {(29, y, 0) for y in range(3, 5)}
        edges = {
            (cell, (cell[0] + dx, cell[1] + dy, 0))
            for cell in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (cell[0] + dx, cell[1] + dy, 0) in cells
        }
        geometry = prepare_geometry(dict(map_id=777, cells=cells, edges=edges))
        origin = (1, 1, 0)
        result = compact_encounter(
            geometry,
            origin,
            [(2, 6, 0), (3, 6, 0)],
            minimum_cells=36,
            minimum_dimensions=(6, 6),
            spread_opponents=True,
            automatic_cell_budget=1500,
        )
        self.assertEqual(len(result["cells"]), 36)
        self.assertTrue(all(cell[1] < 3 for cell in result["cells"]))
        self.assertTrue(result["edges"] <= edges)
        self.assertEqual(
            reachable(origin, result["cells"], geometry.outgoing), result["cells"]
        )
        self.assertEqual(
            reachable(origin, result["cells"], geometry.incoming), result["cells"]
        )
        self.assertTrue(
            all(
                destination in result["cells"]
                for _, destination in result["participant_positions"]
            )
        )
