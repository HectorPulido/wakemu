"""Automatic transport order requires literal endpoints and directed witnesses."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from extract_native_teleport_flow import extract, topology_for


class NativeTeleportFlowTests(unittest.TestCase):
    def setUp(self):
        self.geometry = dict(
            map_id=7,
            cells=[[0, 0, 0], [1, 0, 0], [10, 0, 0], [11, 0, 0], [20, 0, 0]],
            edges=[
                [[0, 0, 0], [1, 0, 0]],
                [[1, 0, 0], [0, 0, 0]],
                [[10, 0, 0], [11, 0, 0]],
                [[11, 0, 0], [10, 0, 0]],
            ],
        )

    def link(self, identity, x, target, criterion=""):
        return dict(
            id=identity,
            x=x,
            y=0,
            z=0,
            approach_positions=[],
            approach_blocks_center=False,
            destinations=[
                dict(
                    map_id=7,
                    x=target,
                    y=0,
                    z=0,
                    destination_id=identity + 100,
                    criterion=criterion,
                )
            ],
        )

    def test_bidirectional_native_chain_ignores_only_verified_return_to_previous_region(
        self,
    ):
        result = extract(
            self.geometry,
            [],
            [0, 0, 0],
            [self.link(90, 1, 10), self.link(20, 10, 0), self.link(2, 11, 20)],
        )
        self.assertEqual(result["status"], "native_teleport_linear_chain_proved")
        self.assertEqual(
            [s["alternatives"][0]["transport"]["source_id"] for s in result["stages"]],
            [90, 2],
        )

    def test_branch_is_not_sorted_by_id_or_distance(self):
        result = extract(
            self.geometry, [], [0, 0, 0], [self.link(90, 1, 10), self.link(1, 0, 20)]
        )
        self.assertEqual(result["status"], "branched_native_transport_graph")

    def test_nonwalkable_arrival_is_not_snapped(self):
        result = extract(self.geometry, [], [0, 0, 0], [self.link(90, 1, 9)])
        self.assertEqual(result["status"], "unresolved_native_transport_endpoints")

    def test_native_criterion_does_not_automatically_mean_room_victory(self):
        result = extract(self.geometry, [], [0, 0, 0], [self.link(90, 1, 10, "Qf=44")])
        self.assertEqual(result["status"], "physical_sequence_with_unverified_criteria")

    def test_directed_stair_does_not_allow_reverse_approach(self):
        self.geometry["edges"] = [[[1, 0, 0], [0, 0, 0]]]
        result = extract(self.geometry, [], [0, 0, 0], [self.link(90, 1, 10)])
        self.assertEqual(
            result["status"], "directed_native_transport_approach_unreachable"
        )

    def test_generated_topology_preserves_native_arrivals_and_id_independent_order(
        self,
    ):
        transports = [self.link(90, 1, 10), self.link(20, 10, 0), self.link(2, 11, 20)]
        flow = extract(self.geometry, [], [0, 0, 0], transports)
        geometry = dict(
            self.geometry,
            profile=dict(height=6, movement_type=0, jump_capacity=4),
            client_sha256="client",
            topology_sha256="map",
        )
        topology = topology_for(geometry, [], [0, 0, 0], transports, flow)
        self.assertEqual(
            [r["native_arrival"] for r in topology["rooms"]],
            [[0, 0, 0], [10, 0, 0], [20, 0, 0]],
        )
        self.assertEqual(
            [
                (d["source_id"], d["source_room"], d["destination_room"])
                for d in topology["doors"]
            ],
            [(90, 1, 2), (20, 2, 1), (2, 2, 3)],
        )
        self.assertEqual(
            topology["generation_status"],
            "requires_roster_formation_exit_and_dispatch_validation",
        )

    def test_candidate_generation_refuses_an_unresolved_flow(self):
        with self.assertRaises(ValueError):
            topology_for(
                self.geometry,
                [],
                [0, 0, 0],
                [],
                dict(status="branched_native_transport_graph"),
            )
