import struct
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_timeline_snapshot import counters, current_wire_turn, insert


class ControlledSummonWireTurnTests(unittest.TestCase):
    def state(self, actor_id=100):
        fight = Fight(
            77,
            [
                Actor(actor_id, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, (1, 0, 0), 20, 4, 2, 10, 1),
            ],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.ready(1)
        return fight, RuntimeMessages(fight, clock=lambda: 0.0)

    def test_captured_turn_end_packets_use_global_round_not_sy_or_logical_count(self):
        # Actual client 12403 bodies: fight164 first Jamjam turn; fight159
        # later-born Jamjam; fight164 owner after the 16:14:29 SU recovery.
        fixtures = (
            ("00000000000000610001", 1, 1, 1),
            ("00000000000000730002", 2, 1, 2),
            ("00000000000000130002", 2, 3, 2),
        )
        for body_hex, native_round, logical_count, sy_progress in fixtures:
            with self.subTest(body=body_hex):
                actor_id, wire_round = struct.unpack(">qh", bytes.fromhex(body_hex))
                fight, runtime = self.state(actor_id)
                fight.native_timeline_round = native_round
                fight.current.turn_count = logical_count
                counters(fight)[str(actor_id)] = sy_progress
                self.assertEqual(current_wire_turn(fight), wire_round)
                for stale in (wire_round - 1, wire_round + 1):
                    with self.assertRaisesRegex(ValueError, "Stale turn identifier"):
                        runtime.end_turn(1, actor_id, stale)
                with self.assertRaises(ValueError):
                    runtime.end_turn(2, actor_id, wire_round)
                runtime.end_turn(1, actor_id, wire_round)
                self.assertEqual(fight.actors[actor_id].turn_count, logical_count)
                runtime.acknowledge_turn(struct.pack(">i", 1))
                self.assertIsNone(runtime.awaiting_ack)

    def test_late_insertion_before_and_after_current_does_not_change_wire_round(self):
        for slot in (0, 1):
            fight, runtime = self.state()
            fight.native_timeline_round = 3
            counters(fight).pop("100")
            insert(fight, 100, slot)
            self.assertEqual(current_wire_turn(fight), 3)
            self.assertNotEqual(current_wire_turn(fight), counters(fight)["100"] + 1)
            runtime.end_turn(1, 100, 3)
            self.assertEqual(fight.actors[100].turn_count, 1)

    def test_recovery_and_timeout_use_same_native_round(self):
        fight, runtime = self.state()
        fight.native_timeline_round = 2
        fight.current.turn_count = 3
        counters(fight)["100"] = 2
        runtime.recover(1, struct.pack(">i", fight.id), now_ms=0)
        self.assertEqual(current_wire_turn(fight), 2)
        runtime.turn_deadline = -1
        runtime.deadline_turn = fight.turn_id
        self.assertTrue(runtime.expire_current_once())
        self.assertEqual(fight.current.id, -200)
        self.assertEqual(fight.actors[100].turn_count, 3)
