"""Shared native ACK chains preserve real SKIP_TURN presentation boundaries.

The small fixture declares native property1 directly, as test_combat_skip_turn;
it does not claim an original NPC constructor or official client qualification.
"""
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_timeline_snapshot import current_wire_turn


class SharedSkipAckTests(unittest.TestCase):
    def fixture(self):
        one = Session(1, 10, "first", 1134, 0)
        two = Session(2, 20, "second", 1134, 0)
        live = {one, two}
        registry = Registry(lambda session: session in live)
        fight = Fight(
            99,
            [
                Actor(10, 0, (0, 0, 0), 100, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, (3, 0, 0), 100, 6, 3, 95, 1),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(3, 0, 0)}},
        )
        shared = registry.register(fight, one)
        registry.join(
            two,
            struct.pack(">qB", 10, 0),
            Actor(20, 0, (0, 0, 0), 100, 6, 3, 90, 1, 2, True),
            actor_payload=lambda *args: (b"stats", b"effects"),
            bootstrap_packets=lambda *args: (),
        )
        registry.ready(99, one, True, lambda *args: ())
        registry.ready(99, two, True, lambda *args: ())
        npc = shared.fight.actors[-200]
        npc.native_fight_property_counts = {1: 1}
        npc.native_fight_properties = frozenset({1})
        runtime = RuntimeMessages(shared.fight)
        runtime.turn_started()
        shared.runtime = runtime
        self.assertEqual(shared.fight.order, [10, -200, 20])
        for session in (one, two):
            registry.drain(99, session)
        registry.execute(
            99,
            one,
            10,
            lambda candidate, current: current.end_turn(
                1, 10, current_wire_turn(candidate)
            ),
        )
        self.assertEqual((shared.ack.turn, shared.runtime.awaiting_ack), (1, 1))
        self.assertIsNone(shared.runtime.turn_deadline)
        for session in (one, two):
            registry.drain(99, session)
        return registry, shared, one, two

    @staticmethod
    def release(candidate, runtime, body):
        return runtime.acknowledge_turn(body)

    def test_native_skip_rearms_each_owner_barrier_and_failed_publication_is_atomic(
        self,
    ):
        for reject in (False, True):
            with self.subTest(failed_publication=reject):
                registry, shared, one, two = self.fixture()
                ack1, ack2 = struct.pack(">i", 1), struct.pack(">i", 2)
                self.assertFalse(registry.acknowledge(99, one, ack1, self.release))
                self.assertFalse(registry.acknowledge(99, one, ack1, self.release))
                before = (shared.fight, shared.runtime, shared.sequence)
                if reject:
                    original = registry._prepare_accepted
                    observed = []

                    def reject_preparation(current, candidate, runtime, packets):
                        observed.append((candidate.turn_id, runtime.awaiting_ack))
                        raise ValueError("checkpoint rejected")

                    with patch.object(
                        registry, "_prepare_accepted", reject_preparation
                    ):
                        with self.assertRaisesRegex(ValueError, "checkpoint rejected"):
                            registry.acknowledge(99, two, ack1, self.release)
                    self.assertEqual(observed, [(3, 2)])
                    self.assertIs(shared.fight, before[0])
                    self.assertIs(shared.runtime, before[1])
                    self.assertEqual(shared.sequence, before[2])
                    self.assertEqual(shared.ack.received, {1})
                    self.assertEqual(
                        (shared.ack.turn, shared.runtime.awaiting_ack), (1, 1)
                    )
                    self.assertEqual(shared.fight.turn_id, 2)
                    self.assertIsNone(shared.runtime.turn_deadline)
                    self.assertEqual(registry.drain(99, one), [])
                    self.assertEqual(registry.drain(99, two), [])
                self.assertTrue(registry.acknowledge(99, two, ack1, self.release))
                self.assertEqual((shared.ack.turn, shared.runtime.awaiting_ack), (2, 2))
                self.assertEqual(shared.ack.expected, {1: "first", 2: "second"})
                self.assertEqual(shared.ack.received, set())
                self.assertEqual(shared.fight.current.id, 20)
                self.assertEqual(shared.fight.turn_id, 3)
                self.assertIsNone(shared.runtime.turn_deadline)
                self.assertEqual(
                    sum(
                        event["kind"] == "turn_skipped" for event in shared.fight.events
                    ),
                    1,
                )
                left = registry.drain(99, one)
                right = registry.drain(99, two)
                self.assertEqual(
                    [(row.sequence, row.packets) for row in left],
                    [(row.sequence, row.packets) for row in right],
                )
                self.assertEqual(
                    sum(op == 12502 for row in left for op, _ in row.packets), 1
                )
                self.assertFalse(
                    any(
                        op == 13482
                        for row in left
                        for op, body in row.packets
                        if len(body) >= 20
                        and struct.unpack_from(">q", body, 12)[0] == 20
                    )
                )
                with self.assertRaises(ValueError):
                    registry.acknowledge(99, one, ack1, self.release)
                with self.assertRaises(ValueError):
                    registry.acknowledge(
                        99, Session(2, 20, "stale", 1134, 0), ack2, self.release
                    )
                self.assertFalse(registry.acknowledge(99, two, ack2, self.release))
                self.assertIsNone(shared.runtime.turn_deadline)
                self.assertEqual(registry.drain(99, one), [])
                self.assertTrue(registry.acknowledge(99, one, ack2, self.release))
                self.assertIsNone(shared.ack.turn)
                self.assertIsNone(shared.runtime.awaiting_ack)
                self.assertEqual(shared.runtime.deadline_turn, 3)
                self.assertIsNotNone(shared.runtime.turn_deadline)
                self.assertIs(shared.runtime.fight, shared.fight)
                final = registry.drain(99, one)
                self.assertTrue(
                    any(
                        op == 13482 and struct.unpack_from(">q", body, 12)[0] == 20
                        for row in final
                        for op, body in row.packets
                    )
                )
                with self.assertRaises(ValueError):
                    registry.acknowledge(99, one, ack2, self.release)


if __name__ == "__main__":
    unittest.main()
