"""Independent hybrid structure counterexamples, without database or client writes."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_classic_dungeon_hybrid_structure import (
    audit_configuration,
    literal_links,
    walk_reachable,
)


def record(native_type="DUNGEON_2_ROOMS"):
    return dict(
        key="native:1",
        name_es="Dungeon",
        native=dict(id=1, name_fr="Donjon", type=native_type),
        native_objects=[],
        guides=[],
    )


def portal(criterion=""):
    return dict(
        map_id=1,
        id=10,
        x=0,
        y=0,
        z=0,
        approach_positions=[],
        approach_blocks_center=False,
        destinations=[
            dict(
                destination_id=11,
                map_id=1,
                x=10,
                y=0,
                z=0,
                criterion=criterion,
                cyZ=-1,
                cyX=0,
                cyW=0,
            )
        ],
    )


def geometry():
    return dict(
        map_id=1,
        cells=[[0, 0, 0], [10, 0, 0]],
        edges=[],
        client_sha256="client",
        topology_sha256="terrain",
    )


class ClassicHybridAuditTest(unittest.TestCase):
    def test_literal_classic_branch_is_allowed_without_allowing_neo(self):
        links, unresolved = literal_links(geometry(), [portal("not IsNeoServer()")])
        self.assertEqual(len(links), 1)
        links, unresolved = literal_links(geometry(), [portal("IsNeoServer()")])
        self.assertFalse(links)
        self.assertEqual(len(unresolved), 1)

    def test_three_players_is_not_a_three_room_contract(self):
        cfg = dict(
            topology=dict(
                rooms=[dict(order=1, anchor=[0, 0, 0], cells=[[0, 0, 0]])],
                doors=[],
                physical_doors=[],
            )
        )
        result = audit_configuration(
            record("DUNGEON_3_PLAYERS"),
            dict(key="route", entry_map_id=2),
            geometry(),
            [],
            [0, 0, 0],
            cfg,
            scope="test",
            configuration_path="fixture",
        )
        self.assertIsNone(result["native_room_metadata"])
        self.assertFalse(
            any(
                i["code"] == "configured_encounters_fewer_than_native_room_metadata"
                for i in result["issues"]
            )
        )

    def test_missing_transport_has_actual_unreachable_anchor_counterexample(self):
        cfg = dict(
            topology=dict(
                rooms=[
                    dict(order=1, anchor=[0, 0, 0], cells=[[0, 0, 0]]),
                    dict(order=2, anchor=[10, 0, 0], cells=[[10, 0, 0]]),
                ],
                doors=[],
                physical_doors=[],
            )
        )
        result = audit_configuration(
            record(),
            dict(key="route", entry_map_id=2),
            geometry(),
            [portal()],
            [0, 0, 0],
            cfg,
            scope="test",
            configuration_path="fixture",
        )
        failures = [
            i
            for i in result["issues"]
            if i["code"]
            == "encounter_anchor_unreachable_with_configured_gate_transport_bindings"
        ]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["evidence"]["room_order"], 2)
        self.assertEqual(result["structural_fullflow_status"], "blocked")

    def test_bound_transport_reaches_next_stage_after_frontier_opens(self):
        cfg = dict(
            topology=dict(
                rooms=[
                    dict(order=1, anchor=[0, 0, 0], cells=[[0, 0, 0]]),
                    dict(order=2, anchor=[10, 0, 0], cells=[[10, 0, 0]]),
                ],
                doors=[
                    dict(
                        source_id=10,
                        destination_id=11,
                        source_room=1,
                        destination_room=2,
                    )
                ],
                physical_doors=[],
            )
        )
        result = audit_configuration(
            record(),
            dict(key="route", entry_map_id=2),
            geometry(),
            [portal()],
            [0, 0, 0],
            cfg,
            scope="test",
            configuration_path="fixture",
        )
        self.assertEqual(result["structural_fullflow_status"], "passed")
        self.assertTrue(
            all(
                e["configured_frontier_reachable"]
                for e in result["encounter_anchor_evidence"]
            )
        )

    def test_true_gate_free_future_room_bypass_is_reported(self):
        g = geometry()
        g["edges"] = [[[0, 0, 0], [10, 0, 0]]]
        cfg = dict(
            topology=dict(
                rooms=[
                    dict(order=1, anchor=[0, 0, 0], cells=[[0, 0, 0]]),
                    dict(order=2, anchor=[10, 0, 0], cells=[[10, 0, 0]]),
                ],
                doors=[],
                physical_doors=[],
            )
        )
        result = audit_configuration(
            record(),
            dict(key="route", entry_map_id=2),
            g,
            [],
            [0, 0, 0],
            cfg,
            scope="test",
            configuration_path="fixture",
        )
        issue = next(
            i
            for i in result["issues"]
            if i["code"] == "future_room_terrain_reachable_before_its_frontier"
        )
        self.assertEqual(issue["evidence"]["counterexample_position"], [10, 0, 0])
        self.assertEqual(issue["severity"], "review")
        self.assertEqual(
            issue["evidence"]["runtime_validation"]["status"], "unsupported_policy"
        )

    def test_runtime_rejected_future_path_is_not_labelled_a_confirmed_bypass(self):
        g = geometry()
        g["edges"] = [[[0, 0, 0], [10, 0, 0]]]
        cfg = dict(
            topology=dict(
                policy="native_teleport_victory_policy",
                exploration_geometry=g,
                rooms=[
                    dict(order=1, anchor=[0, 0, 0], cells=[[0, 0, 0]]),
                    dict(order=2, anchor=[10, 0, 0], cells=[[10, 0, 0]]),
                ],
                doors=[],
                physical_doors=[],
            )
        )
        result = audit_configuration(
            record(),
            dict(key="route", entry_map_id=2),
            g,
            [],
            [0, 0, 0],
            cfg,
            scope="test",
            configuration_path="fixture",
        )
        issue = next(
            i
            for i in result["issues"]
            if i["code"] == "future_room_terrain_reachable_before_its_frontier"
        )
        self.assertEqual(issue["severity"], "review")
        self.assertEqual(issue["evidence"]["runtime_validation"]["status"], "rejected")

    def test_runtime_accepted_future_path_has_concrete_bypass_witness(self):
        g = geometry()
        g["edges"] = [[[0, 0, 0], [10, 0, 0]]]
        cfg = dict(
            topology=dict(
                policy="native_physical_door_victory_policy",
                exploration_geometry=g,
                rooms=[
                    dict(order=1, anchor=[0, 0, 0], cells=[[0, 0, 0]]),
                    dict(order=2, anchor=[10, 0, 0], cells=[[10, 0, 0]]),
                ],
                doors=[],
                physical_doors=[],
            )
        )
        result = audit_configuration(
            record(),
            dict(key="route", entry_map_id=2),
            g,
            [],
            [0, 0, 0],
            cfg,
            scope="test",
            configuration_path="fixture",
        )
        issue = next(
            i
            for i in result["issues"]
            if i["code"] == "future_room_terrain_reachable_before_its_frontier"
        )
        self.assertEqual(issue["severity"], "high")
        self.assertEqual(issue["evidence"]["runtime_validation"]["status"], "accepted")
        self.assertEqual(
            issue["evidence"]["runtime_validation"]["path"], [[0, 0, 0], [10, 0, 0]]
        )

    def test_configured_encounters_above_native_metadata_are_reviewed_symmetrically(
        self,
    ):
        g = dict(
            map_id=1,
            cells=[[0, 0, 0], [1, 0, 0], [2, 0, 0]],
            edges=[[[0, 0, 0], [1, 0, 0]], [[1, 0, 0], [2, 0, 0]]],
            client_sha256="client",
            topology_sha256="terrain",
        )
        cfg = dict(
            topology=dict(
                policy="native_teleport_victory_policy",
                exploration_geometry=g,
                rooms=[
                    dict(order=i + 1, anchor=[i, 0, 0], cells=[[i, 0, 0]])
                    for i in range(3)
                ],
                doors=[],
                physical_doors=[],
            )
        )
        result = audit_configuration(
            record("DUNGEON_2_ROOMS"),
            dict(key="route", entry_map_id=2),
            g,
            [],
            [0, 0, 0],
            cfg,
            scope="test",
            configuration_path="fixture",
        )
        issue = next(
            i
            for i in result["issues"]
            if i["code"] == "configured_encounters_exceed_native_room_metadata"
        )
        self.assertEqual(issue["severity"], "review")
        self.assertEqual(issue["evidence"]["configured_encounters"], 3)
        self.assertEqual(issue["evidence"]["native_room_metadata"], 2)

    def test_declared_simplified_arena_never_passes_full_progression_audit(self):
        cfg = dict(
            topology=dict(
                rooms=[dict(order=1, anchor=[0, 0, 0], cells=[[0, 0, 0]])],
                doors=[],
                physical_doors=[],
            )
        )
        result = audit_configuration(
            record("DUNGEON_3_PLAYERS"),
            dict(key="route", entry_map_id=2),
            geometry(),
            [],
            [0, 0, 0],
            cfg,
            scope="prepared_simplified_final_arena",
            configuration_path="fixture",
        )
        self.assertEqual(result["structural_fullflow_status"], "needs_manual_review")
        self.assertTrue(
            any(
                i["code"] == "declared_simplified_final_arena_not_full_progression"
                for i in result["issues"]
            )
        )


if __name__ == "__main__":
    unittest.main()
