"""Regression checks for safe generic local dungeon topology discovery."""

import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "dungeon_route_discovery",
    Path(__file__).resolve().parents[1] / "tools/discover_dungeon_native_routes.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def grid_geometry(width=14, height=14):
    cells = [(x, y, 0) for x in range(width) for y in range(height)]
    cell_set = set(cells)
    edges = []
    for x, y, z in cells:
        for neighbor in ((x + 1, y, z), (x, y + 1, z)):
            if neighbor in cell_set:
                edges.extend([((x, y, z), neighbor), (neighbor, (x, y, z))])
    return {"map_id": 77, "cells": cells, "edges": edges}


class DungeonNativeRouteDiscoveryTests(unittest.TestCase):
    def test_topology_is_deterministic_and_capacity_checked(self):
        geometry = grid_geometry()
        entry = {"x": 0, "y": 0, "z": 0}
        first = MODULE.accessible_anchor_topology(
            geometry, entry, 3, enemy_counts=[3, 5, 6]
        )
        second = MODULE.accessible_anchor_topology(
            geometry, entry, 3, enemy_counts=[3, 5, 6]
        )
        self.assertEqual(first, second)
        self.assertEqual("local_accessible_anchor_policy", first["policy"])
        self.assertFalse(first["official_room_order_verified"])
        rooms = first["rooms"]
        self.assertEqual([1, 2, 3], [room["order"] for room in rooms])
        self.assertEqual(
            [3, 5, 6], [room["validated_enemy_capacity"] for room in rooms]
        )
        self.assertTrue(all(room["validated_party_capacity"] == 6 for room in rooms))
        all_room_cells = [tuple(cell) for room in rooms for cell in room["cells"]]
        self.assertEqual(len(all_room_cells), len(set(all_room_cells)))
        self.assertTrue(set(all_room_cells) <= set(geometry["cells"]))
        anchors = [tuple(room["anchor"]) for room in rooms]
        self.assertEqual(len(anchors), len(set(anchors)))
        self.assertTrue(set(anchors) <= set(geometry["cells"]))

    def test_tiny_disconnected_decoration_is_not_selected(self):
        geometry = grid_geometry()
        decoration = [(30, 0, 0), (31, 0, 0), (32, 0, 0)]
        geometry["cells"].extend(decoration)
        topology = MODULE.accessible_anchor_topology(
            geometry, {"x": 0, "y": 0, "z": 0}, 2, enemy_counts=[3, 4]
        )
        selected = {tuple(cell) for room in topology["rooms"] for cell in room["cells"]}
        self.assertFalse(selected & set(decoration))
        self.assertTrue(selected <= set(grid_geometry()["cells"]))

    def test_unknown_room_count_and_unfit_encounter_fail_closed(self):
        geometry = grid_geometry()
        entry = {"x": 0, "y": 0, "z": 0}
        with self.assertRaisesRegex(ValueError, "Known positive room count"):
            MODULE.accessible_anchor_topology(geometry, entry, 0)
        with self.assertRaisesRegex(ValueError, "Invalid per-room encounter capacity"):
            MODULE.accessible_anchor_topology(geometry, entry, 1, enemy_counts=[0])
        with self.assertRaisesRegex(ValueError, "Native terrain has fewer cells"):
            MODULE.accessible_anchor_topology(
                geometry, entry, len(geometry["cells"]) + 1
            )
        with self.assertRaisesRegex(ValueError, "capacity"):
            MODULE.accessible_anchor_topology(geometry, entry, 1, enemy_counts=[200])


if __name__ == "__main__":
    unittest.main()
