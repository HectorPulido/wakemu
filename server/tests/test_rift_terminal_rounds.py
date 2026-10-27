"""Full forty-cycle core timeline, with both real terminal end-turn routes.

These minimal FSM actors qualify the terminal scheduler/ACK contract, not boss
characteristics, source graphs or loot. Native boss flows are covered separately.
"""
import struct
import unittest


class RiftTerminalRoundsTests(unittest.TestCase):
    def test_forty_real_cycles_close_player_and_server_end_without_future_ack(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_timeline_snapshot import current_wire_turn

        endings = set()
        for player_first in (False, True):
            with self.subTest(player_first=player_first):
                player = Actor(
                    7,
                    0,
                    (0, 0, 0),
                    100,
                    6,
                    3,
                    100 if player_first else 10,
                    1,
                    owner_id=3,
                    controlled=True,
                )
                enemy = Actor(
                    -200, 1, (2, 0, 0), 100, 6, 3, 10 if player_first else 100, 1
                )
                fight = Fight(
                    77,
                    [player, enemy],
                    {(0, 0, 0), (1, 0, 0), (2, 0, 0)},
                    {0: {(0, 0, 0)}, 1: {(2, 0, 0)}},
                )
                fight.rift_wave_state = dict(instance_id=1, wave=1, turn_budget=40)
                fight.ready(3)
                runtime = RuntimeMessages(fight, clock=lambda: 100.0)
                runtime.turn_started()
                completed = 0
                while runtime.fight.phase == "active":
                    self.assertLess(completed, 81)
                    current = runtime.fight.current
                    previous = runtime.fight.turn_id
                    packets = (
                        runtime.end_turn(
                            3, current.id, current_wire_turn(runtime.fight)
                        )
                        if current.controlled
                        else runtime.end_server_turn(current.id, previous)
                    )
                    completed += 1
                    self.assertIn(12502, [opcode for opcode, _ in packets])
                    if runtime.fight.phase == "finished":
                        endings.add(current.controlled)
                        self.assertNotIn(13337, [opcode for opcode, _ in packets])
                        self.assertNotIn(13482, [opcode for opcode, _ in packets])
                        break
                    self.assertEqual(runtime.awaiting_ack, previous)
                    runtime.acknowledge_turn(struct.pack(">i", previous))
                self.assertEqual(completed, 80)
                self.assertEqual(runtime.fight.native_timeline_round, 41)
                self.assertEqual(runtime.fight.winner, 0)
                self.assertEqual(runtime.fight.rift_wave_state["outcome"], "survived")
                self.assertEqual(runtime.pending, [])
                self.assertIsNone(runtime.awaiting_ack)
                self.assertIsNone(runtime.turn_deadline)
                self.assertIsNone(runtime.deadline_turn)
                self.assertIsNone(runtime.fight.current)
                with self.assertRaises(ValueError):
                    runtime.acknowledge_turn(struct.pack(">i", previous))
        self.assertEqual(endings, {False, True})
