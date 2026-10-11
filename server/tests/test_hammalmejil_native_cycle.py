import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prepare_hammalmejil_native_cycle import reviewed_cycle


class HammalmejilCycleTests(unittest.TestCase):
    def graph(self):
        links = []
        for source_id, a, b in ((19112, 3, 12), (19109, 5, 12), (19110, 3, 5)):
            for source, target in ((a, b), (b, a)):
                links.append(
                    dict(
                        kind="physical_gate",
                        source_id=source_id,
                        source_region=source,
                        destination_region=target,
                    )
                )
        return dict(entry_region=12, reachable_regions=[3, 5, 12], links=links)

    def test_literal_cycle_retains_three_native_arenas(self):
        graph = self.graph()
        original = copy.deepcopy(graph)
        result = reviewed_cycle(graph)
        self.assertEqual(result["native_visit_regions"], [12, 5, 3, 12])
        self.assertEqual(result["stage_by_region"], {12: 1, 5: 2, 3: 3})
        self.assertEqual(graph, original)

    def test_rejects_invented_gate(self):
        graph = self.graph()
        graph["links"][0]["source_id"] = 999
        with self.assertRaises(ValueError):
            reviewed_cycle(graph)

    def test_rejects_extra_reachable_arena(self):
        graph = self.graph()
        graph["reachable_regions"].append(99)
        with self.assertRaises(ValueError):
            reviewed_cycle(graph)

    def test_rejects_wrong_native_entry(self):
        graph = self.graph()
        graph["entry_region"] = 3
        with self.assertRaises(ValueError):
            reviewed_cycle(graph)
