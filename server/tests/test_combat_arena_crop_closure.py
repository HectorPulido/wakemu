import unittest
from unittest.mock import patch

from wakfu_server.combat.combat_arena_selection import (
    MAX_CELL_BUDGET,
    compact_encounter,
)
from wakfu_server.combat.combat_geometry import encounter_component
from wakfu_server.combat.combat_wire import arena


def crop_closure_topology():
    """An irregular native patch with a real hole and unsafe nearby surfaces."""
    missing_hole = (1, 1, 0)
    disconnected = (0, 4, 0)
    one_way = (0, 7, 0)
    cells = {
        (x, y, 0)
        for x in range(8)
        for y in range(8)
        if (x, y, 0) not in {missing_hole, disconnected, one_way}
    }
    # Keep these exported surfaces inside the crop bounds, but outside the
    # player's unambiguous mutual component.
    cells.update((disconnected, one_way, (4, 4, 2)))

    edges = []
    for cell in cells:
        if cell in {disconnected, one_way, (4, 4, 2)}:
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            target = (cell[0] + dx, cell[1] + dy, 0)
            if target in cells and target != disconnected:
                edges.append((cell, target))

    # The extra reachable altitude makes this XY ambiguous, so both heights
    # must be pruned from the encounter component.
    for floor in ((3, 4, 0), (4, 3, 0)):
        edges.extend(((floor, (4, 4, 2)), ((4, 4, 2), floor)))

    # A directed drop is exported at (0, 7), but it has no return edge.
    edges.append(((1, 7, 0), one_way))
    return (
        {"map_id": 312, "cells": cells, "edges": edges},
        missing_hole,
        disconnected,
        one_way,
    )


def select_fallback(data):
    # Three remote original positions force the encounter's spread policy;
    # their old world positions are intentionally not part of this local map.
    with patch(
        "wakfu_server.combat.combat_arena_selection._rectangular_encounter",
        return_value=None,
    ):
        return compact_encounter(
            data,
            (3, 3, 0),
            [(20, 20, 0), (21, 20, 0), (22, 20, 0)],
            spread_opponents=True,
        )


def mask_at(wire_arena, cell):
    index = (
        (cell[1] - wire_arena["y"]) * wire_arena["width"] + cell[0] - wire_arena["x"]
    )
    return wire_arena["cell_masks"][index]


class ArenaCropClosureTests(unittest.TestCase):
    def test_fallback_closes_crop_over_native_component_and_clears_valid_wire_mask(
        self,
    ):
        data, missing_hole, disconnected, one_way = crop_closure_topology()
        result = select_fallback(data)

        xmin, ymin, xmax, ymax = result["bounds"]
        crop_area = (xmax - xmin + 1) * (ymax - ymin + 1)
        self.assertLessEqual(crop_area, MAX_CELL_BUDGET)
        self.assertGreater(len(result["cells"]), 36)

        component, _ = encounter_component(data, (3, 3, 0))
        native_component_in_bounds = {
            cell
            for cell in component
            if xmin <= cell[0] <= xmax and ymin <= cell[1] <= ymax
        }
        self.assertTrue(native_component_in_bounds <= result["cells"])

        # This valid native cell lies in the old BFS prefix's crop hole. It
        # must be playable after closure, while missing/unsafe cells stay blocked.
        self.assertIn((0, 0, 0), result["cells"])
        self.assertNotIn(missing_hole, result["cells"])
        self.assertNotIn(disconnected, result["cells"])
        self.assertNotIn(one_way, result["cells"])

        wire = arena(312, 1, sorted(result["cells"]), result["placement"])
        self.assertEqual(mask_at(wire, (0, 0, 0)), 0)
        self.assertEqual(mask_at(wire, missing_hole), 256)
        self.assertEqual(mask_at(wire, disconnected), 256)
        self.assertEqual(mask_at(wire, one_way), 256)

    def test_fallback_keeps_missing_one_way_disconnected_and_ambiguous_out(self):
        data, missing_hole, disconnected, one_way = crop_closure_topology()
        result = select_fallback(data)

        self.assertEqual(result["blocked_ambiguous"], {(4, 4)})
        self.assertNotIn((4, 4, 0), result["cells"])
        self.assertNotIn((4, 4, 2), result["cells"])
        self.assertNotIn(missing_hole, result["cells"])
        self.assertNotIn(disconnected, result["cells"])
        self.assertNotIn(one_way, result["cells"])
        self.assertLessEqual(
            (result["bounds"][2] - result["bounds"][0] + 1)
            * (result["bounds"][3] - result["bounds"][1] + 1),
            MAX_CELL_BUDGET,
        )


if __name__ == "__main__":
    unittest.main()
