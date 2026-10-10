"""A lethal current-actor action must finish presentation before successor AI."""
import struct
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_runtime_messages import RuntimeMessages


class DefeatedTurnAckTests(unittest.TestCase):
    def setUp(self):
        self.owner = Session(1, 10, "owner", 1134, 0)
        self.registry = Registry(lambda session: session == self.owner)
        fight = Fight(
            99,
            [
                Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(115, 0, (1, 0, 0), 20, 6, 3, 90, 1, 1, True),
                Actor(-200, 1, (3, 0, 0), 20, 4, 2, 1, 1),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(3, 0, 0)}},
        )
        self.shared = self.registry.register(
            fight, self.owner, runtime=RuntimeMessages(fight)
        )
        fight.ready(1)
        fight.order = [115, -200, 10]
        fight.turn_index = 0
        fight.actors[115].turn_count = 1

    def acknowledge(self, turn):
        return self.registry.acknowledge(
            99,
            self.owner,
            struct.pack(">i", turn),
            lambda fight, runtime, body: runtime.acknowledge_turn(body),
        )

    def test_self_defeat_waits_for_old_turn_ack_then_ai_ack_then_owner(self):
        def lethal(fight, runtime):
            fight.apply_damage(115, 115, 20)
            return [(12727, b"existing-lethal-presentation")]

        self.registry.execute(99, self.owner, 115, lethal)
        self.assertEqual(self.shared.fight.current.id, -200)
        self.assertEqual(self.shared.runtime.awaiting_ack, 1)
        self.assertEqual(self.shared.ack.turn, 1)
        self.assertIsNone(self.shared.runtime.turn_deadline)
        self.assertTrue(self.shared.runtime.pending)
        packets = self.registry.drain(99, self.owner)[0].packets
        self.assertEqual(packets[0], (12727, b"existing-lethal-presentation"))
        self.assertEqual([op for op, _ in packets].count(12502), 1)
        self.assertNotIn(13482, [op for op, _ in packets])
        with self.assertRaisesRegex(ValueError, "synchronization pending"):
            self.registry.execute_server(
                99,
                -200,
                lambda fight, runtime: runtime.end_server_turn(-200, fight.turn_id),
                expected_sequence=self.shared.sequence,
            )
        self.assertTrue(self.acknowledge(1))
        self.assertIsNone(self.shared.runtime.awaiting_ack)
        self.assertFalse(self.shared.runtime.pending)
        self.registry.execute_server(
            99,
            -200,
            lambda fight, runtime: runtime.end_server_turn(-200, fight.turn_id),
            expected_sequence=self.shared.sequence,
        )
        self.assertEqual(self.shared.ack.turn, 2)
        self.assertEqual(self.shared.runtime.awaiting_ack, 2)
        self.assertTrue(self.acknowledge(2))
        self.assertEqual(self.shared.fight.current.id, 10)
        self.assertIsNone(self.shared.ack.turn)
        self.assertIsNotNone(self.shared.runtime.turn_deadline)

    def test_legacy_arm_preserves_received_owner_ack(self):
        self.shared.runtime.awaiting_ack = 7
        self.registry.arm_ack(99, 7)
        self.shared.ack.received.add(1)
        self.registry.arm_ack(99, 7)
        self.assertEqual(self.shared.ack.received, {1})

    def test_conflicting_pending_ack_rolls_back_action(self):
        self.shared.runtime.awaiting_ack = 7
        self.registry.arm_ack(99, 7)

        def invalid(fight, runtime):
            fight.actors[10].hp -= 1
            runtime.awaiting_ack = 8
            return [(12873, b"must-not-publish")]

        with self.assertRaisesRegex(ValueError, "replaced a pending"):
            self.registry.execute(99, self.owner, 115, invalid)
        self.assertEqual(self.shared.fight.actors[10].hp, 60)
        self.assertEqual(self.shared.runtime.awaiting_ack, 7)
        self.assertEqual(self.shared.ack.turn, 7)
        self.assertFalse(self.shared.outboxes[1])


if __name__ == "__main__":
    unittest.main()
