"""Selected-surface perimeter masks preserve native geometry and indices."""
import unittest
from wakfu_server.combat_arena_selection import cardinal_border_cells
from wakfu_server.combat_wire import arena


class ArenaBorderTests(unittest.TestCase):
    def test_perimeter_is_selected_cells_only_and_never_replaces_surface_index(self):
        cells = {(x, y, 7) for x in range(3) for y in range(3)}
        borders = cardinal_border_cells(cells)
        self.assertEqual(len(borders), 8)
        self.assertNotIn((1, 1, 7), borders)
        result = arena(
            1,
            1,
            sorted(cells),
            {0: {(1, 1, 7)}, 1: {(2, 1, 7)}},
            surface_indices={c[:2]: 3 for c in cells},
            border_cells=borders,
        )
        self.assertEqual(result["cell_masks"][4], 3)
        self.assertEqual(result["cell_masks"][0], 131)
        self.assertTrue(all((mask & 768) == 0 for mask in result["cell_masks"]))

    def test_hole_and_narrow_corridor_do_not_invent_border_terrain(self):
        cells = {(x, y, 0) for x in range(5) for y in range(5)} - {(2, 2, 0)}
        borders = cardinal_border_cells(cells)
        self.assertIn((2, 1, 0), borders)
        self.assertNotIn((2, 2, 0), borders)
        with self.assertRaisesRegex(ValueError, "selected surface"):
            arena(
                1,
                1,
                sorted(cells),
                {0: {(0, 0, 0)}, 1: {(4, 4, 0)}},
                border_cells={(2, 2, 0)},
            )
