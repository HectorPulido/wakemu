"""Reviewed native room selection must not include a larger exterior region."""
import importlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "discover_dungeon_native_routes",
    Path(__file__).resolve().parents[1] / "tools/discover_dungeon_native_routes.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


encounters = importlib.import_module("wakfu_server.maps.dungeon_encounters")


class ReviewedRoomSelectionTests(unittest.TestCase):
    def geometry(self):
        cells = [(x, y, 0) for x in range(11) for y in range(3)]
        cells += [(x, y, 0) for x in range(100, 120) for y in range(5)]
        owned = set(cells)
        edges = [
            (a, (a[0] + dx, a[1] + dy, 0))
            for a in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (a[0] + dx, a[1] + dy, 0) in owned
        ]
        return dict(map_id=312, cells=cells, edges=edges)

    @patch.object(encounters, "enemy_formation", return_value=[])
    def test_reviewed_rooms_exclude_larger_exterior_and_native_door_cells(self, _):
        doors = [dict(x=5, y=y, z=0) for y in range(3)]
        result = module.accessible_anchor_topology(
            self.geometry(),
            dict(x=0, y=0, z=0),
            2,
            enemy_counts=[3, 3],
            reviewed_room_anchors=[(0, 0, 0), (10, 0, 0)],
            native_doors=doors,
        )
        self.assertEqual([len(room["cells"]) for room in result["rooms"]], [15, 15])
        self.assertTrue(all(cell[0] < 5 for cell in result["rooms"][0]["cells"]))
        self.assertTrue(all(5 < cell[0] < 100 for cell in result["rooms"][1]["cells"]))

    def test_same_component_cannot_be_claimed_twice(self):
        with self.assertRaisesRegex(ValueError, "distinct native rooms"):
            module.accessible_anchor_topology(
                self.geometry(),
                dict(x=0, y=0, z=0),
                2,
                enemy_counts=[3, 3],
                reviewed_room_anchors=[(0, 0, 0), (1, 0, 0)],
                native_doors=[dict(x=5, y=y, z=0) for y in range(3)],
            )

    @patch.object(encounters, "enemy_formation", return_value=[])
    def test_default_component_selection_remains_unchanged(self, _):
        result = module.accessible_anchor_topology(
            self.geometry(),
            dict(x=0, y=0, z=0),
            2,
            enemy_counts=[3, 3],
        )
        self.assertEqual(len(result["rooms"][0]["cells"]), 100)
        self.assertEqual(len(result["rooms"][1]["cells"]), 33)
