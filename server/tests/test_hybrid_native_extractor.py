"""Independent regressions for generic physical-plus-teleport extraction."""
import json
from pathlib import Path
import unittest

from extract_hybrid_native_dungeon_flow import extract, main_spine

ROOT = Path(__file__).resolve().parents[2]


class HybridNativeExtractorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geometry = json.loads(
            (
                ROOT
                / ".runtime/local/all-native-dungeon-exploration/exploration-1266.json"
            ).read_text()
        )
        cls.candidate = json.loads(
            (
                ROOT
                / ".runtime/local/milubo-four-room-mixed-v6-20261010/native_dungeon_47.json"
            ).read_text()
        )
        cls.transports = json.loads(
            (
                ROOT
                / ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
            ).read_text()
        )

    def milubo(self, gates=True):
        rows = self.candidate["topology"]["physical_doors"] if gates else ()
        objects = [
            dict(
                type="Door",
                id=door["source_id"],
                map_id=1266,
                x=door["position"][0],
                y=door["position"][1],
                z=door["position"][2],
            )
            for door in rows
        ]
        return extract(self.geometry, objects, self.transports, [0, 0, 0], 1264)

    def test_milubo_rejoins_literal_physical_gates_and_recovers_all_native_rooms(self):
        graph = self.milubo()
        spine = main_spine(graph, 4)
        self.assertEqual(spine["encounter_regions"], [9, 0, 16, 6])
        self.assertEqual(len(spine["encounter_regions"]), 4)
        self.assertEqual(len(spine["stage_by_region"]), 7)
        self.assertEqual(graph["reachable_regions"], [0, 6, 9, 13, 14, 15, 16])
        gate_links = [
            link for link in graph["links"] if link["kind"].startswith("physical")
        ]
        self.assertEqual(len(gate_links), 4)  # both directions across each gate
        self.assertEqual({link["source_id"] for link in gate_links}, {32205, 32212})

    def test_missing_gate_join_reproduces_incomplete_reachability(self):
        graph_without_gates = self.milubo(gates=False)
        graph_with_gates = self.milubo(gates=True)
        # Teleports alone reach a subset, but miss native room 16 and do not
        # reproduce the reviewed four-encounter path.
        self.assertNotIn(16, graph_without_gates["reachable_regions"])
        self.assertIn(16, graph_with_gates["reachable_regions"])
        self.assertNotEqual(
            main_spine(graph_without_gates, 4)["encounter_regions"],
            [9, 0, 16, 6],
        )

    def test_all_literal_transport_sources_and_transit_regions_are_retained(self):
        graph = self.milubo()
        transport_links = [
            link for link in graph["links"] if link["kind"] == "native_transport"
        ]
        expected_internal = {32206, 32207, 32208, 32209, 32210, 32213, 32214, 32215}
        self.assertEqual(
            {link["source_id"] for link in transport_links}, expected_internal
        )
        exits = {link["source_id"] for link in graph["exits"]}
        self.assertEqual(exits, {32204, 32211})
        spine = main_spine(graph, 4)
        self.assertEqual(set(spine["region_path"]), {9, 13, 0, 15, 14, 16, 6})
        self.assertEqual(set(spine["encounter_regions"]), {9, 0, 16, 6})
        self.assertEqual(set(spine["stage_by_region"]), set(spine["region_path"]))

    def test_conflicting_optional_branch_stage_is_rejected(self):
        graph = dict(
            entry_region=0,
            component_sizes=[10, 5, 1, 1, 1],
            exits=[dict(source_region=3, matches_entry_exterior=True)],
            reachable_regions=[0, 1, 2, 3, 4],
            links=[
                dict(source_region=0, destination_region=1),
                dict(source_region=1, destination_region=2),
                dict(source_region=2, destination_region=3),
                dict(source_region=0, destination_region=4),
                dict(source_region=2, destination_region=4),
            ],
        )
        with self.assertRaisesRegex(
            ValueError, "contradictory encounter-stage attachments"
        ):
            main_spine(graph, 3)
