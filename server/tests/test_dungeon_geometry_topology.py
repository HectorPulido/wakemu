"""Offline topology evidence tests, including published native extraction."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "extract_dungeon_topology", ROOT / "server/tools/extract_dungeon_topology.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def geometry(cells, edges):
    return {"map_id": 1, "cells": cells, "edges": edges}


class DungeonGeometryTopologyTests(unittest.TestCase):
    def test_exact_door_separates_corridor(self):
        a, b, c = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        door = dict(id=10, type="Door", x=1, y=0, z=0)
        result = MODULE.analyze(geometry([a, b, c], [(a, b), (b, c)]), [door], [a])
        self.assertEqual(result["closed_region_sizes"], [1, 1])
        self.assertTrue(result["doors"][0]["candidate_separator"])
        self.assertEqual(result["asymmetric_native_edges"], 2)

    def test_door_with_bypass_does_not_prove_gate(self):
        a, b, c, d = (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)
        door = dict(id=10, type="Door", x=1, y=0, z=0)
        result = MODULE.analyze(
            geometry([a, b, c, d], [(a, b), (b, c), (c, d), (d, a)]), [door]
        )
        self.assertFalse(result["doors"][0]["candidate_separator"])

    def test_missing_door_cell_never_snaps_to_nearby(self):
        a, b = (0, 0, 0), (1, 0, 0)
        door = dict(id=10, type="Door", x=1, y=0, z=1)
        result = MODULE.analyze(geometry([a, b], [(a, b)]), [door])
        self.assertFalse(result["doors"][0]["exact_cell_walkable"])
        self.assertEqual(result["closed_region_sizes"], [2])

    def test_invalid_export_edge_rejected(self):
        with self.assertRaisesRegex(ValueError, "leaves walkable"):
            MODULE.analyze(geometry([(0, 0, 0)], [((0, 0, 0), (1, 0, 0))]), [])

    def test_native_tofu_entry_remains_unresolved(self):
        report = json.loads((ROOT / "docs/reports/dungeons/topology.json").read_text())
        row = next(r for r in report["maps"] if r["map_id"] == 1087)
        doors = {d["object_id"]: d for d in row["doors"]}
        self.assertFalse(doors[26873]["candidate_separator"])
        self.assertEqual(doors[26874]["adjacent_closed_regions"], [1, 8])
        self.assertEqual(doors[26875]["adjacent_closed_regions"], [8, 9])
        self.assertEqual(row["entries"][0]["closed_region"], 4)
        self.assertNotIn(
            4, {r for d in row["doors"] for r in d["adjacent_closed_regions"]}
        )

    def test_native_jalato_links_three_large_regions(self):
        report = json.loads((ROOT / "docs/reports/dungeons/topology.json").read_text())
        row = next(r for r in report["maps"] if r["map_id"] == 1086)
        links = {
            (t["source_region"], t["destination_region"])
            for t in row["teleport_links"]
            if t["destination_map"] == 1086
        }
        self.assertEqual(links, {(0, 5), (5, 0), (5, 3), (3, 5)})
        self.assertFalse(row["doors"])


if __name__ == "__main__":
    unittest.main()
