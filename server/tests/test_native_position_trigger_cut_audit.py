import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_native_position_trigger_cuts import analyze


class TriggerCutsTests(unittest.TestCase):
    def test_parallel_nonadjacent_triggers_require_complete_bundle(self):
        a, b, c, d = (0, 0, 0), (1, 1, 0), (1, -1, 0), (2, 0, 0)
        edges = []
        for x, y in [(a, b), (b, d), (a, c), (c, d)]:
            edges.extend([[x, y], [y, x]])
        objects = [
            dict(id=i, type="PositionTrigger", x=p[0], y=p[1], z=p[2])
            for i, p in [(1, b), (2, c)]
        ]
        result = analyze(dict(cells=[a, b, c, d], edges=edges), objects)
        bundle = result["bundles"][0]
        self.assertEqual(bundle["object_ids"], [1, 2])
        self.assertTrue(bundle["nonadjacent_members"])
        self.assertTrue(
            all(w["closed_unreachable"] for w in bundle["directed_witnesses"])
        )
        self.assertFalse(
            any(w["alone_separates_any_witness"] for w in bundle["single_cut_checks"])
        )

    def test_off_terrain_trigger_is_not_snapped(self):
        result = analyze(
            dict(cells=[[0, 0, 0]], edges=[]),
            [dict(id=1, type="PositionTrigger", x=0, y=0, z=1)],
        )
        self.assertFalse(result["triggers"][0]["literal_walkable"])
        self.assertEqual(result["status"], "no_literal_separator_proved")

    def test_tiny_regions_are_retained(self):
        cells = [[0, 0, 0], [1, 0, 0], [2, 0, 0]]
        result = analyze(
            dict(cells=cells, edges=[[cells[0], cells[1]], [cells[1], cells[2]]]),
            [dict(id=1, type="PositionTrigger", x=1, y=0, z=0)],
        )
        self.assertEqual(result["all_trigger_cut_component_sizes"], [1, 1])
        self.assertEqual(len(result["bundles"][0]["directed_witnesses"]), 1)


if __name__ == "__main__":
    unittest.main()
