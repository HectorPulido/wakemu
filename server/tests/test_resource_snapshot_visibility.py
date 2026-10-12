"""Resource appearance replay follows each peer's native partition window."""
from contextlib import contextmanager
import unittest
from unittest.mock import patch

from wakfu_server import planting_runtime


class FakeStore:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    @contextmanager
    def connection(self):
        yield self

    def execute(self, query, parameters):
        self.queries.append((query, parameters))
        return self.rows


class ResourceSnapshotVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"x": -19, "y": 0, "resource_uid": 1},
            {"x": -18, "y": 0, "resource_uid": 2},
            {"x": 0, "y": 0, "resource_uid": 3},
            {"x": 35, "y": 35, "resource_uid": 4},
            {"x": 36, "y": 0, "resource_uid": 5},
        ]
        self.store = FakeStore(self.rows)
        self.plantings = planting_runtime.Plantings(self.store)
        self.packet = patch.object(
            planting_runtime.planting,
            "resource_packet",
            side_effect=lambda row: (13135, row["resource_uid"]),
        )
        self.packet.start()
        self.addCleanup(self.packet.stop)

    def test_native_three_by_three_window_and_negative_boundaries(self):
        position = {"map_id": 1385, "instance_id": 0, "x": 0, "y": 0}
        self.assertEqual(
            self.plantings.snapshots(1385, 0, position=position),
            [(13135, 2), (13135, 3), (13135, 4)],
        )
        self.assertEqual(self.store.queries[0][1], (1385, 0))

    def test_movement_replays_newly_visible_resources_without_global_dedup(self):
        first = {"map_id": 1385, "instance_id": 0, "x": 0, "y": 0}
        moved = dict(first, x=18)
        self.plantings.snapshots(1385, 0, position=first)
        expected = [(13135, 3), (13135, 4), (13135, 5)]
        self.assertEqual(self.plantings.snapshots(1385, 0, position=moved), expected)
        self.assertEqual(self.plantings.snapshots(1385, 0, position=moved), expected)

    def test_foreign_map_or_instance_rejected_before_query(self):
        for position in (
            {"map_id": 1386, "instance_id": 0, "x": 0, "y": 0},
            {"map_id": 1385, "instance_id": 99, "x": 0, "y": 0},
        ):
            with self.assertRaises(ValueError):
                self.plantings.snapshots(1385, 0, position=position)
        self.assertEqual(self.store.queries, [])

    def test_omitted_position_preserves_offline_complete_snapshot(self):
        self.assertEqual(
            self.plantings.snapshots(1385, 0),
            [(13135, row["resource_uid"]) for row in self.rows],
        )


if __name__ == "__main__":
    unittest.main()
