"""Directed witnesses must combine real walk edges and literal transports."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from extract_milubo_mixed_flow import hybrid_path


class MixedNativePathTests(unittest.TestCase):
    def setUp(self):
        self.edges = [
            ([0, 0, 0], [1, 0, 0]),
            ([1, 0, 0], [2, 0, -1]),
            ([10, 0, -8], [11, 0, -8]),
        ]
        self.transport = dict(
            source_id=5,
            destination_id=9,
            native_approach_cells=[[2, 0, -1]],
            destination_position=[10, 0, -8],
        )

    def test_real_physical_gate_then_literal_transport_connect_disjoint_walk_components(
        self,
    ):
        witness = hybrid_path(self.edges, [self.transport], [0, 0, 0], [11, 0, -8])
        self.assertEqual(
            [s["kind"] for s in witness], ["walk", "walk", "native_transport", "walk"]
        )
        self.assertEqual(witness[2]["source_id"], 5)

    def test_closed_physical_gate_prevents_reaching_transport(self):
        self.assertIsNone(
            hybrid_path(
                self.edges,
                [self.transport],
                [0, 0, 0],
                [11, 0, -8],
                blocked=[[1, 0, 0]],
            )
        )

    def test_absent_transport_never_becomes_a_guessed_walk_edge(self):
        self.assertIsNone(hybrid_path(self.edges, [], [0, 0, 0], [11, 0, -8]))

    def test_native_transport_and_walk_edges_are_directed(self):
        self.assertIsNone(
            hybrid_path(self.edges, [self.transport], [11, 0, -8], [0, 0, 0])
        )


class ReviewedMiluboArtifactTests(unittest.TestCase):
    def setUp(self):
        import json

        root = Path(__file__).resolve().parents[2]
        evidence = json.loads(
            (
                root
                / "docs/reports/dungeons/MILUBO-FOUR-ROOM-MIXED-CANDIDATE-20261010.json"
            ).read_text()
        )["records"][0]
        path = root / evidence["path"]
        if not path.is_file():
            self.skipTest("Prepared read-only native Milubo configuration required")
        self.config = json.loads(path.read_text())
        self.evidence = evidence

    def test_four_reviewed_initial_encounters_and_final_boss_are_preserved(self):
        plan = self.config["compiled_plan"]
        rooms = plan["rooms"]
        self.assertEqual(len(rooms), 4)
        self.assertEqual(
            [sum(m["count"] for m in r["monsters"]) for r in rooms], [6, 7, 8, 8]
        )
        self.assertEqual(
            [
                sum(m["count"] * m["native_min_level"] for m in r["monsters"])
                for r in rooms
            ],
            [424, 494, 562, 575],
        )
        self.assertEqual(
            [
                (r["order"], m["ref_id"], m["count"])
                for r in rooms
                for m in r["monsters"]
                if m["role"] == "boss"
            ],
            [(4, 5114, 1)],
        )
        self.assertEqual(
            {m["ref_id"] for r in rooms for m in r["monsters"]},
            {5111, 5112, 5113, 5114},
        )

    def test_native_mixed_frontier_blocks_each_unwon_encounter(self):
        topology = self.config["topology"]
        edges = topology["exploration_geometry"]["edges"]
        self.assertEqual(topology["rooms"][0]["native_arrival"], [0, 0, 0])
        self.assertEqual(
            {d["source_id"] for d in topology["physical_doors"]}, {32205, 32212}
        )
        self.assertEqual(len(topology["doors"]), 8)
        for room in topology["rooms"][1:]:
            stage = room["order"]
            blocked = [
                d["position"]
                for d in topology["physical_doors"]
                if d["destination_room"] >= stage
            ]
            allowed = [
                d
                for d in topology["doors"]
                if max(d["source_room"], d["destination_room"]) < stage
            ]
            self.assertIsNone(
                hybrid_path(edges, allowed, [0, 0, 0], room["anchor"], blocked=blocked)
            )
