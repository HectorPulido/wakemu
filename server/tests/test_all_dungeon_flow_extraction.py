"""Offline batch flow evidence refuses guessed arrivals and premature exits."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from extract_all_dungeon_flows import classify, reachable


class AllDungeonFlowExtractionTests(unittest.TestCase):
    def setUp(self):
        self.cells = [[i, 0, 0] for i in range(7)]
        self.edges = []
        for a, b in zip(self.cells, self.cells[1:]):
            self.edges.extend([[a, b], [b, a]])
        self.geometry = dict(map_id=99, cells=self.cells, edges=self.edges)
        self.doors = [
            dict(id=20, type="Door", x=2, y=0, z=0),
            dict(id=40, type="Door", x=4, y=0, z=0),
        ]

    def test_linear_native_flow_preserves_first_closed_room(self):
        result = classify(self.geometry, self.doors, [0, 0, 0], [[6, 0, 0]], [])
        self.assertEqual(result["status"], "physical_linear_chain_proved")
        self.assertEqual(
            result["first_encounter_reachable_cells"], [[0, 0, 0], [1, 0, 0]]
        )
        self.assertEqual(result["directed_physical_flows"][0]["door_chain"], [20, 40])

    def test_exit_in_entry_room_cannot_authorize_full_dungeon_flow(self):
        result = classify(self.geometry, self.doors, [0, 0, 0], [[1, 0, 0]], [])
        self.assertEqual(result["status"], "physical_flow_review")
        self.assertTrue(result["manual_review"])

    def test_internal_teleport_prevents_automatic_physical_policy_generation(self):
        teleports = [
            dict(id=90, x=1, y=0, z=0, destinations=[dict(map_id=99, x=6, y=0, z=0)])
        ]
        result = classify(self.geometry, self.doors, [0, 0, 0], [[6, 0, 0]], teleports)
        self.assertEqual(result["status"], "mixed_transport_physical_review")
        self.assertTrue(result["manual_review"])

    def test_nonwalkable_native_arrival_is_not_snapped_to_nearest_cell(self):
        result = classify(self.geometry, self.doors, [0, 0, 1], [[6, 0, 0]], [])
        self.assertEqual(result["status"], "entry_not_walkable")

    def test_directed_reachability_does_not_invent_reverse_stairs(self):
        self.assertEqual(reachable([[[0, 0, 0], [1, 0, -4]]], [1, 0, -4]), {(1, 0, -4)})

    def test_literal_teleports_stay_reviewable_without_unlock_authority(self):
        teleports = [
            dict(id=90, x=1, y=0, z=0, destinations=[dict(map_id=99, x=6, y=0, z=0)])
        ]
        result = classify(self.geometry, [], [0, 0, 0], [], teleports)
        self.assertEqual(result["status"], "native_transport_graph_review")
        self.assertEqual(result["topology"]["teleport_links"][0]["source_id"], 90)
