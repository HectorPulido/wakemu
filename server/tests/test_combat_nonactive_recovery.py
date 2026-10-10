"""Delayed recovery requests must not revive or overwrite nonactive phases."""
import struct
import unittest

from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Actor, Fight


class NonactiveRecoveryTests(unittest.TestCase):
    def runtime(self):
        actors = [
            Actor(13, 0, (0, 0, 0), 100, 6, 3, 100, 1, 2, True),
            Actor(-20, 1, (1, 0, 0), 46, 6, 6, 10, 1),
        ]
        fight = Fight(
            136,
            actors,
            {a.position for a in actors},
            {0: {actors[0].position}, 1: {actors[1].position}},
        )
        return RuntimeMessages(fight, clock=lambda: 0)

    def test_placement_recovery_preserves_roster_and_pending_presentation(self):
        runtime = self.runtime()
        runtime.pending = [(13420, b"placement presentation")]
        self.assertIsNone(runtime.fight.current)
        self.assertEqual(runtime.recover(2, struct.pack(">i", 136), now_ms=1), [])
        self.assertEqual(runtime.fight.phase, "placement")
        self.assertEqual(set(runtime.fight.actors), {13, -20})
        self.assertEqual(runtime.pending, [(13420, b"placement presentation")])
        self.assertIsNone(runtime.turn_deadline)

    def test_terminal_recovery_does_not_drop_terminal_batch_or_arm_turn(self):
        runtime = self.runtime()
        runtime.fight.phase = "finished"
        runtime.pending = [(12238, b"terminal presentation")]
        runtime.awaiting_ack = 2
        runtime.action_id = 12
        self.assertEqual(runtime.recover(2, struct.pack(">i", 136), now_ms=1), [])
        self.assertEqual(runtime.fight.phase, "finished")
        self.assertIsNone(runtime.fight.current)
        self.assertEqual(runtime.awaiting_ack, 2)
        self.assertEqual(runtime.pending, [(12238, b"terminal presentation")])
        self.assertEqual(runtime.action_id, 12)
        self.assertIsNone(runtime.turn_deadline)

    def test_nonactive_recovery_still_rejects_foreign_owner_or_fight(self):
        runtime = self.runtime()
        for owner, body in (
            (9, struct.pack(">i", 136)),
            (2, struct.pack(">i", 135)),
            (2, b""),
        ):
            with self.subTest(owner=owner, body=body):
                with self.assertRaises(ValueError):
                    runtime.recover(owner, body, now_ms=1)
        self.assertEqual(runtime.fight.phase, "placement")
        self.assertIsNone(runtime.turn_deadline)
