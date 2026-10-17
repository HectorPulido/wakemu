"""Real Registry transitions replay shared queues and collective ACK fencing."""
from collections import deque
import copy
import json
import struct
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Registry, SharedFight, Session, Batch
from wakfu_server.combat_shared_reproduction import (
    capture_shared_state,
    restore_shared_state,
    replay_execute,
    replay_acknowledge,
    ObservedLeaseTape,
    lease_result,
    LeaseReplayMismatch,
    UnsupportedSharedReproduction,
)
from wakfu_server.combat_reproduction import controlled_environment
from wakfu_server.combat_timeline_snapshot import current_wire_turn


CLOCKS = {"wall_time_ns": 1700000000000000000, "monotonic_ns": 0}
POLICIES = {"WAKFU_NATIVE_AREA_CALLBACKS": "1", "WAKFU_NATIVE_GRANTED_CAST": "0"}


def bind_clock(runtime, shared):
    runtime.clock = lambda: 0.0


def end_current(fight, runtime):
    actor = fight.current
    return runtime.end_turn(actor.owner_id, actor.id, current_wire_turn(fight))


class SharedReproductionTests(unittest.TestCase):
    def setUp(self):
        self.one = Session(1, 100, "first", 1134, 0)
        self.two = Session(2, 200, "second", 1134, 0)
        actors = [
            Actor(100, 0, (0, 0, 0), 60, 6, 3, 1000, 1, 1, True),
            Actor(200, 0, (1, 0, 0), 60, 6, 3, 900, 1, 2, True),
            Actor(-200, 1, (2, 0, 0), 20, 4, 2, 100, 1),
        ]
        fight = Fight(
            88,
            actors,
            {actor.position for actor in actors},
            {0: {actors[0].position, actors[1].position}, 1: {actors[2].position}},
        )
        fight.ready(1)
        fight.ready(2)
        self.shared = SharedFight(
            fight, 1134, 0, RuntimeMessages(fight, clock=lambda: 0.0)
        )
        self.shared.participants = {1: self.one, 2: self.two}
        self.shared.connected = {1, 2}
        self.shared.outboxes = {1: deque(), 2: deque()}
        self.rows = []

        def live(session):
            value = session in (self.one, self.two)
            self.rows.append(lease_result(session, result=value))
            return value

        self.registry = Registry(live)
        self.registry.fights[fight.id] = self.shared
        self.registry.by_actor = {actor.id: fight.id for actor in actors}
        self.registry.by_character = {100: fight.id, 200: fight.id}

    def snapshot(self):
        return capture_shared_state(self.shared, registry=self.registry)

    def restore(self, payload, rows=None):
        return restore_shared_state(
            json.loads(json.dumps(payload)),
            self.rows if rows is None else rows,
            bind_runtime=bind_clock,
        )

    def end_turn(self):
        with controlled_environment(CLOCKS, POLICIES):
            return self.registry.execute(88, self.one, 100, end_current)

    def test_roundtrip_preserves_aliases_mailboxes_and_fresh_isolation(self):
        batch = Batch(0, ((12847, b"bootstrap"),))
        self.shared.outboxes[1].append(batch)
        self.shared.outboxes[2].append(batch)
        self.shared.join_context = {
            "leaders": {0: 100},
            "hero_appearance": lambda source: (12608, b"appearance"),
        }
        payload = self.snapshot()
        registry, shared, tape = self.restore(payload, [])
        self.assertIs(shared.runtime.fight, shared.fight)
        self.assertIs(shared.outboxes[1][0], shared.outboxes[2][0])
        self.assertIsNot(shared.lock, self.shared.lock)
        self.assertIsNot(shared.dispatch_lock, self.shared.dispatch_lock)
        self.assertIsNot(shared.outboxes[1], self.shared.outboxes[1])
        self.assertIn(
            "reproduction_omitted_service", shared.join_context["hero_appearance"]
        )
        self.assertEqual(capture_shared_state(shared, registry=registry), payload)
        shared.fight.actors[100].hp = 1
        shared.outboxes[1].clear()
        self.assertEqual(self.shared.fight.actors[100].hp, 60)
        self.assertEqual(len(self.shared.outboxes[1]), 1)
        tape.assert_consumed()

    def test_actual_end_turn_replays_barrier_live_checks_and_recipient_batches(self):
        before = self.snapshot()
        live_result = self.end_turn()
        self.assertEqual([row["session"]["account_id"] for row in self.rows], [1, 1, 2])
        expected = self.snapshot()
        restored = self.restore(before)
        with controlled_environment(CLOCKS, POLICIES):
            result = replay_execute(restored, self.one, 100, end_current)
        registry, shared, _ = restored
        self.assertEqual(result, live_result)
        self.assertEqual(capture_shared_state(shared, registry=registry), expected)
        self.assertEqual(shared.ack.expected, {1: "first", 2: "second"})
        self.assertEqual(shared.outboxes[1][-1].packets, shared.outboxes[2][-1].packets)
        self.assertIn(
            12502, [opcode for opcode, body in shared.outboxes[1][-1].packets]
        )
        self.assertEqual(self.shared.ack.received, set())

    def test_native_checkpoint_preserves_attribute_order_and_binds_scalar_key_services(
        self,
    ):
        from wakfu_server.combat_npc_reproduction import after_comparison

        payload = capture_shared_state(
            self.shared, registry=self.registry, preserve_scalars=True
        )
        registry, restored, tape = self.restore(payload, [])
        self.assertEqual(list(vars(restored.fight)), list(vars(self.shared.fight)))
        self.assertEqual(list(vars(restored.runtime)), list(vars(self.shared.runtime)))
        self.assertIs(restored.runtime.fight, restored.fight)
        self.assertTrue(callable(restored.runtime.clock))
        self.assertEqual(restored.runtime.clock(), 0.0)
        recaptured = capture_shared_state(
            restored, registry=registry, preserve_scalars=True
        )
        # Rebuilding the outer diagnostic envelope creates fresh scalar keys.
        # Native object order and aliases above must still restore exactly.
        comparison = after_comparison(payload["graph"], recaptured["graph"])
        self.assertTrue(comparison["scalar_value_matches"], comparison)
        with self.assertRaisesRegex(UnsupportedSharedReproduction, "trusted binding"):
            restore_shared_state(payload, [], bind_runtime=lambda runtime, shared: None)
        tape.assert_consumed()

    def test_native_turn_claim_is_preserved_as_private_coordination_data(self):
        self.shared.native_ai_turn_claim = (
            -200,
            self.shared.fight.turn_id,
            "private-claim-nonce",
        )
        payload = self.snapshot()
        registry, restored, tape = self.restore(payload, [])
        self.assertEqual(
            restored.native_ai_turn_claim, self.shared.native_ai_turn_claim
        )
        self.assertEqual(capture_shared_state(restored, registry=registry), payload)
        tape.assert_consumed()

    def test_partial_then_final_ack_replay_actual_runtime_once(self):
        self.end_turn()
        body = struct.pack(">i", self.shared.ack.turn)
        for session, released in ((self.one, False), (self.two, True)):
            before = self.snapshot()
            self.rows.clear()
            sequence = self.shared.sequence
            with controlled_environment(CLOCKS, POLICIES):
                result = self.registry.acknowledge(
                    88,
                    session,
                    body,
                    lambda fight, runtime, request: runtime.acknowledge_turn(request),
                )
            expected = self.snapshot()
            restored = self.restore(before)
            with controlled_environment(CLOCKS, POLICIES):
                replayed = replay_acknowledge(restored, session, body)
            registry, shared, _ = restored
            self.assertIs(result, released)
            self.assertIs(replayed, released)
            self.assertEqual(capture_shared_state(shared, registry=registry), expected)
            if not released:
                self.assertEqual(shared.sequence, sequence)
                self.assertEqual(shared.ack.received, {1})
                self.assertIsNotNone(shared.runtime.awaiting_ack)
            else:
                self.assertEqual(shared.sequence, sequence + 1)
                self.assertIsNone(shared.ack.turn)
                self.assertIsNone(shared.runtime.awaiting_ack)
                self.assertEqual(shared.runtime.pending, [])

    def test_failed_ordinary_final_ack_preserves_actual_received_mutation(self):
        self.end_turn()
        body = struct.pack(">i", self.shared.ack.turn)
        self.registry.acknowledge(
            88, self.one, body, lambda *args: self.fail("First ACK released")
        )
        before = self.snapshot()
        self.rows.clear()
        prior_runtime, prior_fight = self.shared.runtime, self.shared.fight

        def reject(*args):
            raise ValueError("native release rejected")

        with self.assertRaisesRegex(ValueError, "native release rejected"):
            self.registry.acknowledge(88, self.two, body, reject)
        self.assertIs(self.shared.runtime, prior_runtime)
        self.assertIs(self.shared.fight, prior_fight)
        self.assertEqual(self.shared.ack.received, {1, 2})
        expected = self.snapshot()
        restored = self.restore(before)
        with self.assertRaisesRegex(ValueError, "native release rejected"):
            replay_acknowledge(restored, self.two, body, release_packets=reject)
        registry, shared, _ = restored
        self.assertEqual(capture_shared_state(shared, registry=registry), expected)

    def test_stale_session_rejection_replays_without_mutating_shared_state(self):
        stale = Session(1, 100, "old-generation", 1134, 0)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Stale combat session lease"):
            self.registry.execute(88, stale, 100, end_current)
        restored = self.restore(before)
        with self.assertRaisesRegex(ValueError, "Stale combat session lease"):
            replay_execute(restored, stale, 100, end_current)
        registry, shared, _ = restored
        self.assertEqual(capture_shared_state(shared, registry=registry), before)

    def test_lease_tape_requires_exact_session_order_errors_and_full_consumption(self):
        tape = ObservedLeaseTape(
            [lease_result(self.one, result=True), lease_result(self.two, result=False)]
        )
        with self.assertRaisesRegex(LeaseReplayMismatch, "identity/order"):
            tape(self.two)
        self.assertTrue(tape(self.one))
        with self.assertRaisesRegex(LeaseReplayMismatch, "unused"):
            tape.assert_consumed()
        self.assertFalse(tape(self.two))
        tape.assert_consumed()
        with self.assertRaisesRegex(LeaseReplayMismatch, "unobserved"):
            tape(self.one)
        for error in (RuntimeError("database unavailable"), KeyError("missing")):
            tape = ObservedLeaseTape([lease_result(self.one, error=error)])
            with self.assertRaises(type(error)) as observed:
                tape(self.one)
            self.assertEqual(observed.exception.args, error.args)
            self.assertEqual(str(observed.exception), str(error))
            tape.assert_consumed()
        with self.assertRaisesRegex(LeaseReplayMismatch, "additional native fields"):
            ObservedLeaseTape(
                [lease_result(self.one, error=OSError(2, "missing", "/private/path"))]
            )

    def test_unknown_boundaries_services_and_schema_reject_explicitly(self):
        payload = self.snapshot()
        with self.assertRaisesRegex(UnsupportedSharedReproduction, "trusted binding"):
            restore_shared_state(payload, [])
        for mutation in (
            lambda shared: setattr(shared, "future_lifecycle", {}),
            lambda shared: setattr(shared.fight, "rift_wave_state", {"wave": 1}),
            lambda shared: setattr(
                shared, "join_context", {"rift_accepted_action": lambda *args: None}
            ),
            lambda shared: setattr(
                shared.runtime, "fight", copy.deepcopy(shared.fight)
            ),
        ):
            with self.subTest(mutation=mutation):
                restored = self.restore(payload, [])
                mutation(restored[1])
                with self.assertRaises(UnsupportedSharedReproduction):
                    capture_shared_state(restored[1])
        broken = copy.deepcopy(payload)
        broken["boundary"] = "restore-live-sockets"
        with self.assertRaises(UnsupportedSharedReproduction):
            restore_shared_state(broken, [])

    def test_malformed_membership_and_mailbox_types_reject(self):
        from wakfu_server.combat_reproduction_state import decode_state, encode_state

        payload = self.snapshot()
        for mutate in (
            lambda state: state["connected"].add("99"),
            lambda state: state["outboxes"].update({2: []}),
            lambda state: state["outboxes"].update(
                {1: (Batch("99", ((13420, b"x"),)),)}
            ),
            lambda state: state["ack"].received.add("1"),
        ):
            state = decode_state(payload["graph"])
            mutate(state)
            broken = dict(payload, graph=encode_state(state))
            with self.assertRaises(UnsupportedSharedReproduction):
                self.restore(broken, [])

    def test_stale_ack_generation_is_preserved_for_actual_native_rejection(self):
        self.end_turn()
        self.shared.ack.expected[1] = "stale-generation"
        before = self.snapshot()
        self.rows.clear()
        body = struct.pack(">i", self.shared.ack.turn)
        with self.assertRaisesRegex(ValueError, "Foreign/stale turn ACK owner"):
            self.registry.acknowledge(88, self.one, body, lambda *args: [])
        restored = self.restore(before)
        with self.assertRaisesRegex(ValueError, "Foreign/stale turn ACK owner"):
            replay_acknowledge(restored, self.one, body)
        registry, shared, _ = restored
        self.assertEqual(shared.ack.expected[1], "stale-generation")
        self.assertEqual(capture_shared_state(shared, registry=registry), before)

    def test_typed_corrupt_barrier_and_mailboxes_are_not_sanitized(self):
        self.shared.ack.expected = {1: "stale-generation"}
        self.shared.ack.received = {2}
        self.shared.connected.add(99)
        self.shared.outboxes.pop(2)
        self.shared.outboxes[1].extend([Batch(99, ()), Batch(-1, ())])
        payload = self.snapshot()
        registry, shared, _ = self.restore(payload, [])
        self.assertEqual(capture_shared_state(shared, registry=registry), payload)


if __name__ == "__main__":
    unittest.main()
