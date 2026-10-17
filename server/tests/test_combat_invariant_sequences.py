"""Runtime delivery and participant ACK checks inspect exact owned state."""
import copy
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_ack_barrier import AckBarrier
from wakfu_server.combat_invariant_observation import (
    invariant_observation_scope,
    observe_prepared_boundary,
)
from wakfu_server.combat_invariants import Boundary, check_prepared_boundary
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Session
from wakfu_server.combat_state import Actor, Fight


class CombatInvariantSequenceTests(unittest.TestCase):
    def fixture(self):
        player = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        fight = Fight(
            880,
            (player, npc),
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        runtime = RuntimeMessages(
            fight, clock=lambda: self.fail("clock read during inspection")
        )
        session = Session(3, 7, "active-generation", 1134, 0)
        return fight, runtime, session

    @staticmethod
    def barrier(turn, session):
        ack = AckBarrier()
        ack.arm(turn, (session,))
        return ack

    @staticmethod
    def report(fight, runtime, ack):
        return check_prepared_boundary(
            fight, runtime, Boundary("sequence-test", "prepared"), ack=ack
        )

    @staticmethod
    def sequence_findings(report):
        return [row for row in report.findings if row.invariant.startswith("sequence.")]

    def test_pending_previous_turn_ack_is_valid_after_timeline_advances(self):
        fight, runtime, session = self.fixture()
        fight.turn_id = 5
        runtime.awaiting_ack = 4
        runtime.pending = [(12613, b"previous-turn-delivery")]
        ack = self.barrier(4, session)

        report = self.report(fight, runtime, ack)
        self.assertFalse(
            [row for row in self.sequence_findings(report) if row.status == "violation"]
        )
        self.assertIn("sequence.shared_ack", report.checked)
        self.assertEqual(ack.expected, {session.account_id: session.generation})

    def test_pending_packets_without_runtime_ack_are_rejected(self):
        fight, runtime, _session = self.fixture()
        runtime.pending = [(12613, b"unfenced-packet")]

        report = self.report(fight, runtime, AckBarrier())
        self.assertTrue(
            any(row.invariant == "sequence.pending" for row in report.violations)
        )

    def test_duplicate_native_delivery_identity_is_rejected(self):
        fight, runtime, session = self.fixture()
        runtime.native_action_id = 1
        runtime.last_native_delivery = (
            {"native_action_id": 1},
            {"native_action_id": 1},
        )
        runtime.awaiting_ack = 2
        ack = self.barrier(2, session)

        report = self.report(fight, runtime, ack)
        self.assertTrue(
            any(
                row.invariant == "sequence.native_delivery" for row in report.violations
            )
        )

    def test_stale_barrier_turn_and_stale_generation_receipt_are_rejected(self):
        fight, runtime, session = self.fixture()
        runtime.awaiting_ack = 9
        stale_turn = self.barrier(8, session)
        report = self.report(fight, runtime, stale_turn)
        self.assertTrue(
            any(row.invariant == "sequence.shared_ack" for row in report.violations)
        )

        active = self.barrier(8, session)
        stale_session = Session(3, 7, "previous-generation", 1134, 0)
        with self.assertRaisesRegex(ValueError, "Foreign/stale"):
            active.accept(stale_session, struct.pack(">i", 8))
        self.assertEqual(active.received, set())
        runtime.awaiting_ack = 8
        current_report = self.report(fight, runtime, active)
        self.assertFalse(
            [
                row
                for row in self.sequence_findings(current_report)
                if row.status == "violation"
            ]
        )

    def test_cleared_barrier_cannot_retain_receipts(self):
        fight, runtime, session = self.fixture()
        ack = AckBarrier()
        ack.expected[session.account_id] = session.generation
        ack.received.add(session.account_id)

        report = self.report(fight, runtime, ack)
        self.assertTrue(
            any(row.invariant == "sequence.shared_ack" for row in report.violations)
        )

    def test_empty_pending_barrier_is_valid(self):
        fight, runtime, _session = self.fixture()
        report = self.report(fight, runtime, AckBarrier())
        self.assertFalse(
            [row for row in self.sequence_findings(report) if row.status == "violation"]
        )

    def test_observer_receives_the_staged_next_ack_without_releasing_it(self):
        fight, runtime, session = self.fixture()
        runtime.awaiting_ack = 6
        ack = self.barrier(6, session)
        with invariant_observation_scope() as scope:
            observe_prepared_boundary(
                fight, runtime, operation="Registry.execute", ack=ack
            )
        report = scope.require_boundary("Registry.execute")[0]
        self.assertEqual(report.boundary.stage, "pre_adoption")
        self.assertFalse(
            [row for row in self.sequence_findings(report) if row.status == "violation"]
        )
        self.assertEqual(ack.turn, runtime.awaiting_ack)

    def test_duplicate_unallocated_logical_ids_are_allowed_and_inspection_is_read_only(
        self,
    ):
        fight, runtime, session = self.fixture()
        runtime.awaiting_ack = 3
        duplicate_unallocated = (12613, struct.pack(">iii", fight.id, 3, -1))
        runtime.pending = [duplicate_unallocated, duplicate_unallocated]
        ack = self.barrier(3, session)
        runtime_snapshot = {
            name: copy.deepcopy(value)
            for name, value in vars(runtime).items()
            if name not in ("clock", "fight")
        }
        ack_snapshot = copy.deepcopy(vars(ack))
        pending_identity = id(runtime.pending)

        with patch.object(
            runtime,
            "prepare_delivery",
            side_effect=AssertionError("inspection must not allocate native IDs"),
        ), patch.object(
            AckBarrier,
            "release",
            side_effect=AssertionError("inspection must not release ACK barriers"),
        ), patch.object(
            AckBarrier,
            "accept",
            side_effect=AssertionError("inspection must not accept ACKs"),
        ):
            report = self.report(fight, runtime, ack)

        self.assertFalse(
            [row for row in self.sequence_findings(report) if row.status == "violation"]
        )
        self.assertEqual(id(runtime.pending), pending_identity)
        self.assertEqual(
            runtime.pending, [duplicate_unallocated, duplicate_unallocated]
        )
        self.assertEqual(ack_snapshot, vars(ack))
        for name, value in runtime_snapshot.items():
            self.assertEqual(getattr(runtime, name), value)


if __name__ == "__main__":
    unittest.main()
