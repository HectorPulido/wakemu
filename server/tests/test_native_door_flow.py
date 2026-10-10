"""Directed physical door-flow proofs and native Tofu regression evidence."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))
from extract_native_door_flow import extract, shortest_path


class NativeDoorFlowTests(unittest.TestCase):
    def test_direction_and_blocking_preserved(self):
        a, b, c = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        edges = [(a, b), (b, c)]
        self.assertEqual(shortest_path(edges, a, c), [a, b, c])
        self.assertIsNone(shortest_path(edges, c, a))
        self.assertIsNone(shortest_path(edges, a, c, [b]))

    def test_linear_gate_requires_opening(self):
        cells = [(i, 0, 0) for i in range(5)]
        edges = [edge for a, b in zip(cells, cells[1:]) for edge in ((a, b), (b, a))]
        doors = [
            dict(id=10, type="Door", x=1, y=0, z=0),
            dict(id=20, type="Door", x=3, y=0, z=0),
        ]
        r = extract(
            dict(map_id=1, cells=cells, edges=edges), doors, cells[0], cells[-1]
        )
        self.assertEqual(r["status"], "physical_linear_chain_proved")
        self.assertEqual(r["door_chain"], [10, 20])
        self.assertEqual(
            [s["exit_reachable"] for s in r["stages"]], [False, False, True]
        )

    def test_branch_never_implies_arbitrary_order(self):
        cells = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (-1, 0, 0), (-2, 0, 0)]
        edges = [
            edge
            for a, b in (
                (cells[0], cells[1]),
                (cells[1], cells[2]),
                (cells[0], cells[3]),
                (cells[3], cells[4]),
            )
            for edge in ((a, b), (b, a))
        ]
        doors = [
            dict(id=10, type="Door", x=1, y=0, z=0),
            dict(id=20, type="Door", x=-1, y=0, z=0),
        ]
        r = extract(dict(map_id=1, cells=cells, edges=edges), doors, cells[0], cells[2])
        self.assertEqual(r["status"], "branched_region_graph")

    def test_native_tofu_player_profile_resolves_entry_and_gate_order(self):
        r = json.loads(
            (ROOT / "docs/reports/dungeons/TOFU-NATIVE-FLOW.json").read_text()
        )
        self.assertEqual(r["status"], "physical_linear_chain_proved")
        self.assertEqual(
            r["profile"],
            dict(height=6, movement_type=0, jump_capacity=4, native_class="Sm"),
        )
        self.assertEqual(r["door_chain"], [26874, 26875])
        self.assertEqual(
            [s["exit_reachable"] for s in r["stages"]], [False, False, True]
        )
        path = r["stages"][-1]["directed_exit_path"]
        self.assertEqual(path[0], [14, -25, 0])
        self.assertEqual(path[-1], [33, -5, -12])
        self.assertTrue(any(abs(a[2] - b[2]) == 4 for a, b in zip(path, path[1:])))
        for a, b in zip(path, path[1:]):
            self.assertEqual(abs(a[0] - b[0]) + abs(a[1] - b[1]), 1)
        self.assertIn([23, -35, -8], path)
        self.assertIn([39, -26, -12], path)


if __name__ == "__main__":
    unittest.main()
