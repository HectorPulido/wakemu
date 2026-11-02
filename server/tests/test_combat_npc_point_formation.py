"""Ordinary point NPC formation respects native placement surfaces."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_arena_selection import compact_encounter
from wakfu_server.combat_walk_surface_policy import native_npc_point_placement_allowed


def grid(width=9, height=9):
    cells = {(x, y, 0) for x in range(width) for y in range(height)}
    edges = [
        (cell, (cell[0] + dx, cell[1] + dy, 0))
        for cell in cells
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if (cell[0] + dx, cell[1] + dy, 0) in cells
    ]
    return {"map_id": 910, "cells": cells, "edges": edges}


class NativeNpcPointFormationTests(unittest.TestCase):
    def test_surface_classifier_uses_last_exact_altitude_and_blocks_native_gates(self):
        columns = SimpleNamespace(
            column=lambda x, y: {
                (1, 1): (SimpleNamespace(z=0, blf=2),),
                (2, 1): (SimpleNamespace(z=0, blf=8),),
                (3, 1): (SimpleNamespace(z=0, blf=16),),
                (4, 1): (SimpleNamespace(z=0, blf=0),),
                (5, 1): (SimpleNamespace(z=0, blf=8), SimpleNamespace(z=0, blf=0)),
            }.get((x, y), ())
        )
        self.assertFalse(native_npc_point_placement_allowed(columns, (1, 1, 0)))
        self.assertFalse(native_npc_point_placement_allowed(columns, (2, 1, 0)))
        self.assertTrue(native_npc_point_placement_allowed(columns, (3, 1, 0)))
        self.assertTrue(native_npc_point_placement_allowed(columns, (4, 1, 0)))
        self.assertTrue(native_npc_point_placement_allowed(columns, (5, 1, 0)))

    def test_compact_selection_relocates_forbidden_point_and_fails_without_eligible_cells(
        self,
    ):
        geometry = grid()
        forbidden = (8, 8, 0)
        before_cells, before_edges = set(geometry["cells"]), list(geometry["edges"])
        allowed = set(geometry["cells"]) - {forbidden}
        selected = compact_encounter(
            geometry,
            (0, 0, 0),
            [forbidden],
            cell_budget=81,
            minimum_cells=25,
            minimum_dimensions=(9, 9),
            member_point_cells=allowed,
        )
        placed = selected["placement"][1][0]
        self.assertNotEqual(placed, forbidden)
        self.assertIn(placed, allowed)
        self.assertEqual(geometry["cells"], before_cells)
        self.assertEqual(geometry["edges"], before_edges)
        with self.assertRaisesRegex(ValueError, "footprint capacity"):
            compact_encounter(
                geometry,
                (0, 0, 0),
                [forbidden],
                cell_budget=81,
                minimum_cells=25,
                minimum_dimensions=(9, 9),
                member_point_cells=set(),
            )
        self.assertEqual(geometry["cells"], before_cells)

    def test_positive_radius_uses_existing_footprint_policy_without_point_filter(self):
        geometry = grid(11, 11)
        original = (8, 8, 0)
        selected = compact_encounter(
            geometry,
            (1, 1, 0),
            [original],
            cell_budget=121,
            minimum_cells=25,
            minimum_dimensions=(11, 11),
            member_radii=[1],
            allow_border_footprints=True,
            member_point_cells=set(),
        )
        self.assertEqual(selected["placement"][1], [original])


if __name__ == "__main__":
    unittest.main()
