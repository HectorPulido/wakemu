"""Native publication, failed preparation and durable recovery fencing."""
from copy import deepcopy
import struct
import unittest
from unittest.mock import patch
import test_combat_shared as shared_fixture
import test_combat_shared_reproduction as replay_fixture
from wakfu_server.combat_delivery_boundary import native_packets
from wakfu_server.combat_reproduction import controlled_environment
from wakfu_server.combat_shared import Session
from wakfu_server.combat_shared_reproduction import (
    capture_shared_state,
    replay_execute,
    replay_acknowledge,
)


class DeliveryBoundaryTests(unittest.TestCase):
    def fixture(self):
        fixture = shared_fixture.SharedCombatTests()
        fixture.setUp()
        fixture.join()
        fixture.registry.drain(99, fixture.one)
        fixture.registry.drain(99, fixture.two)
        return fixture

    def test_native_end_and_collective_ack_replay_preserves_collective_boundary(self):
        outcomes = []
        fixture = replay_fixture.SharedReproductionTests()
        fixture.setUp()
        before = fixture.snapshot()
        with controlled_environment(replay_fixture.CLOCKS, replay_fixture.POLICIES):
            sequence = fixture.registry.execute(
                88, fixture.one, 100, replay_fixture.end_current
            )
            expected = fixture.snapshot()
            restored = fixture.restore(before)
            self.assertEqual(
                replay_execute(restored, fixture.one, 100, replay_fixture.end_current),
                sequence,
            )
            self.assertEqual(
                capture_shared_state(restored[1], registry=restored[0]), expected
            )
            shared = fixture.shared
            self.assertEqual(shared.ack.expected, {1: "first", 2: "second"})
            self.assertIn(12502, [op for op, body in shared.outboxes[1][-1].packets])
            self.assertEqual(
                shared.outboxes[1][-1].packets, shared.outboxes[2][-1].packets
            )
            body = struct.pack(">i", shared.ack.turn)
            for owner, complete in ((fixture.one, False), (fixture.two, True)):
                previous = fixture.snapshot()
                fixture.rows.clear()
                release = lambda fight, runtime, value: runtime.acknowledge_turn(value)
                self.assertEqual(
                    fixture.registry.acknowledge(88, owner, body, release), complete
                )
                expected_ack = fixture.snapshot()
                replay = fixture.restore(previous)
                self.assertEqual(
                    replay_acknowledge(replay, owner, body, release_packets=release),
                    complete,
                )
                self.assertEqual(
                    capture_shared_state(replay[1], registry=replay[0]), expected_ack
                )
            self.assertIsNone(shared.ack.turn)
            self.assertIsNone(shared.runtime.awaiting_ack)
            self.assertEqual(shared.sequence, 2)
            outcomes.append(fixture.snapshot())

    def test_failed_prepared_action_does_not_publish_resources_or_barrier(self):
        fixture = self.fixture()
        fixture.shared.fight.ready(1)
        fixture.shared.fight.ready(2)
        old_fight, old_runtime, old_ack = (
            fixture.shared.fight,
            fixture.shared.runtime,
            fixture.shared.ack,
        )

        def malformed(candidate, runtime):
            candidate.actors[10].hp = 1
            return [(70000, b"invalid")]

        with self.assertRaisesRegex(ValueError, "native opcode/body"):
            fixture.registry.execute(99, fixture.one, 10, malformed)
        self.assertIs(fixture.shared.fight, old_fight)
        self.assertIs(fixture.shared.runtime, old_runtime)
        self.assertIs(fixture.shared.ack, old_ack)
        self.assertEqual(old_fight.actors[10].hp, 60)
        self.assertEqual(fixture.shared.sequence, 1)
        self.assertFalse(fixture.shared.outboxes[1])
        self.assertFalse(fixture.shared.outboxes[2])

    def test_candidate_preparation_failure_keeps_native_end_turn_unpublished(self):
        fixture = replay_fixture.SharedReproductionTests()
        fixture.setUp()
        before = fixture.snapshot()
        with patch(
            "wakfu_server.combat_delivery_boundary.accepted_ack",
            side_effect=ValueError("injected ACK preparation"),
        ), controlled_environment(
            replay_fixture.CLOCKS, replay_fixture.POLICIES
        ), self.assertRaisesRegex(
            ValueError, "injected ACK"
        ):
            fixture.registry.execute(88, fixture.one, 100, replay_fixture.end_current)
        self.assertEqual(fixture.snapshot(), before)

    def test_reconnect_persistence_failure_preserves_owner_and_snapshot_for_retry(self):
        outcomes = []
        fixture = self.fixture()
        fixture.live.remove(fixture.two)
        replacement = Session(2, 20, "new-generation", 1134, 0)
        fixture.live.add(replacement)
        attempts = []
        snapshot = ((12044, b"native-bootstrap"), (12053, b"native-timeline"))

        def bootstrap(fight, shared, owner):
            attempts.append((owner, shared.participants[2]))
            return snapshot

        with self.assertRaisesRegex(ValueError, "durable fence"):
            fixture.registry.takeover(
                99,
                replacement,
                bootstrap,
                persist_takeover=lambda previous: (_ for _ in ()).throw(
                    ValueError("durable fence")
                ),
            )
        self.assertEqual(fixture.shared.participants[2], fixture.two)
        self.assertFalse(fixture.shared.outboxes[2])
        fixture.registry.takeover(
            99,
            replacement,
            bootstrap,
            persist_takeover=lambda previous: self.assertEqual(previous, fixture.two),
        )
        self.assertEqual(
            attempts, [(replacement, fixture.two), (replacement, fixture.two)]
        )
        self.assertEqual(fixture.shared.participants[2], replacement)
        outcomes.append(fixture.registry.drain(99, replacement)[0].packets)
        self.assertEqual(outcomes, [snapshot])

    def test_pending_native_recovery_is_private_until_persistence_succeeds(self):
        from test_combat_reconnect_reconciliation import ReconnectReconciliationTests
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot

        outcomes = []
        fixture = ReconnectReconciliationTests()
        fixture.setUp()
        fixture._prepare_pending_ack_reconnect()
        registry, shared = (fixture.adapter.registry, fixture.shared)
        registry.disconnect(fixture.old)
        fixture.live.remove((1, "generation-old", 10))
        replacement = Session(1, 10, "generation-new", 1134, 0)
        fixture.live.add((1, "generation-new", 10))
        before = fixture._fight_state(shared)
        old_fight, old_runtime = (shared.fight, shared.runtime)
        old_ack = deepcopy(vars(shared.ack))
        old_pending = deepcopy(shared.runtime.pending)
        snapshots = []

        def bootstrap(fight, view, session):
            self.assertIsNot(fight, old_fight)
            self.assertIsNot(view.runtime, old_runtime)
            self.assertIsNone(view.ack.turn)
            self.assertIsNone(view.runtime.awaiting_ack)
            packets = owned_snapshot(
                fight,
                view,
                session,
                actor_payload=lambda *args: (b"current-stats", b"\x00\x00"),
            )
            snapshots.append(packets)
            return packets

        with controlled_environment(replay_fixture.CLOCKS, replay_fixture.POLICIES):
            with self.assertRaisesRegex(RuntimeError, "durable recovery failure"):
                registry.takeover(
                    99,
                    replacement,
                    bootstrap,
                    recover_disconnected=True,
                    persist_takeover=lambda previous: (_ for _ in ()).throw(
                        RuntimeError("durable recovery failure")
                    ),
                )
            self.assertIs(shared.fight, old_fight)
            self.assertIs(shared.runtime, old_runtime)
            self.assertEqual(fixture._fight_state(shared), before)
            self.assertEqual(vars(shared.ack), old_ack)
            self.assertEqual(shared.runtime.pending, old_pending)
            registry.takeover(
                99,
                replacement,
                bootstrap,
                recover_disconnected=True,
                persist_takeover=lambda previous: self.assertEqual(
                    previous, fixture.old
                ),
            )
        self.assertEqual(snapshots[0], snapshots[1])
        delivered = registry.drain(99, replacement)[0].packets
        self.assertEqual(delivered, snapshots[1])
        self.assertIn(12053, [op for op, body in delivered])
        self.assertNotIn(12502, [op for op, body in delivered])
        self.assertIsNone(shared.runtime.awaiting_ack)
        self.assertIsNone(shared.ack.turn)
        self.assertIs(shared.runtime.fight, shared.fight)
        outcomes.append((delivered, fixture._fight_state(shared)))

    def test_private_roster_settlement_failure_retry_and_reconnect_are_identical(self):
        outcomes = []
        fixture = self.fixture()
        fixture.shared.fight.phase = "finished"
        fixture.shared.fight.winner = 0
        good = {1: ((12755, b"private-left"),), 2: ((12755, b"private-right"),)}
        calls = []
        with self.assertRaisesRegex(ValueError, "native opcode/body"):
            fixture.registry.settle_finished(
                99, fixture.one, lambda shared: {1: good[1], 2: ((-1, b"bad"),)}
            )
        self.assertFalse(fixture.shared.settlement_ready)
        self.assertFalse(fixture.shared.outboxes[1])
        self.assertFalse(fixture.shared.outboxes[2])

        def commit(shared):
            calls.append(shared.fight.id)
            return deepcopy(good)

        self.assertTrue(fixture.registry.settle_finished(99, fixture.one, commit))
        self.assertFalse(fixture.registry.settle_finished(99, fixture.one, commit))
        self.assertEqual(calls, [99])
        self.assertTrue(fixture.shared.checkpoint_terminal)
        fixture.live.remove(fixture.two)
        replacement = Session(2, 20, "new-generation", 1134, 0)
        fixture.live.add(replacement)
        fixture.registry.takeover(
            99,
            replacement,
            lambda *args: self.fail("settled reconnect must reuse its private result"),
        )
        outcomes.append(
            (
                fixture.registry.drain(99, fixture.one)[0].packets,
                fixture.registry.drain(99, replacement)[0].packets,
            )
        )
        self.assertFalse(fixture.registry.mark_returned(99, fixture.one))
        self.assertTrue(fixture.registry.mark_returned(99, replacement))
        self.assertNotIn(99, fixture.registry.fights)
        self.assertEqual(outcomes, [(good[1], good[2])])

    def test_missing_owner_is_rejected_before_any_private_result_publication(self):
        fixture = self.fixture()
        fixture.shared.fight.phase = "finished"
        with self.assertRaisesRegex(ValueError, "cover its roster"):
            fixture.registry.settle_finished(
                99, fixture.one, lambda shared: {1: ((12755, b"left"),)}
            )
        self.assertFalse(fixture.shared.settlement_ready)
        self.assertEqual(fixture.shared.settlement_batches, {})
        self.assertFalse(fixture.shared.outboxes[1])
        self.assertFalse(fixture.shared.outboxes[2])

    def test_packet_contract_preserves_order_and_rejects_malformed_shapes(self):
        good = ((12502, b"end"), (13420, b"fence"))
        self.assertEqual(native_packets(iter(good)), good)
        for bad in (
            [(True, b"boolean")],
            [(65536, b"large")],
            [(1, bytearray())],
            [[1, b"list"]],
            [(1,)],
        ):
            with self.subTest(bad=bad), self.assertRaisesRegex(
                ValueError, "native opcode/body"
            ):
                native_packets(bad)


if __name__ == "__main__":
    unittest.main()
