"""A real end callback may settle its current actor before turn synchronization."""
from copy import deepcopy
import struct
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_timeline_snapshot import current_wire_turn


class PreEndDeathTests(unittest.TestCase):
    def fixture(self, controlled=True):
        actors = [
            Actor(
                100,
                0 if controlled else 1,
                (0, 0, 0),
                60,
                6,
                3,
                1000,
                1,
                1 if controlled else None,
                controlled,
            ),
            Actor(101, 0, (1, 0, 0), 60, 6, 3, 900, 1, 1, True),
            Actor(-200, 1, (2, 0, 0), 60, 6, 3, 10, 1),
        ]
        cells = {a.position for a in actors}
        fight = Fight(
            7,
            actors,
            cells,
            {
                team: {actor.position for actor in actors if actor.team == team}
                for team in (0, 1)
            },
        )
        fight.ready(1)
        if not controlled:
            current = fight.current
            fight.end_turn(current.owner_id, current.id, current.turn_count)
        self.assertEqual(fight.current.id, 100)
        return fight

    def test_owned_and_server_end_death_advance_once_and_wait_for_real_ack(self):
        for controlled in (True, False):
            with self.subTest(controlled=controlled):
                fight = self.fixture(controlled)
                before_turn = fight.turn_id
                successor = fight.order[(fight.turn_index + 1) % len(fight.order)]
                calls = []

                def end(candidate, *, actor_id, action_id):
                    calls.append(actor_id)
                    candidate = deepcopy(candidate)
                    actor = candidate.actors[actor_id]
                    candidate.apply_effect_damage(101, actor_id, actor.hp)
                    return candidate, [(13420, struct.pack(">i", candidate.id))]

                runtime = RuntimeMessages(
                    fight, clock=lambda: 0.0, turn_end_provider=end
                )
                packets = (
                    runtime.end_turn(1, 100, current_wire_turn(fight))
                    if controlled
                    else runtime.end_server_turn(100, before_turn)
                )
                self.assertEqual(calls, [100])
                self.assertEqual(fight.turn_id, before_turn + 1)
                self.assertEqual(fight.current.id, successor)
                self.assertEqual(fight.actors[100].hp, 0)
                self.assertEqual([op for op, _ in packets].count(12502), 1)
                self.assertEqual(runtime.awaiting_ack, before_turn)
                self.assertIsNone(runtime.turn_deadline)
                self.assertTrue(runtime.pending)
                runtime.acknowledge_turn(struct.pack(">i", before_turn))
                self.assertEqual(fight.turn_id, before_turn + 1)
                self.assertIsNone(runtime.awaiting_ack)
                self.assertFalse(runtime.pending)
                with self.assertRaises(ValueError):
                    runtime.acknowledge_turn(struct.pack(">i", before_turn))

    def test_alive_or_multiple_transition_callback_rejected_atomically(self):
        for advances in (1, 2):
            with self.subTest(advances=advances):
                fight = self.fixture()
                old_order, old_turn = list(fight.order), fight.turn_id

                def end(candidate, *, actor_id, action_id):
                    candidate = deepcopy(candidate)
                    if advances == 2:
                        candidate.apply_effect_damage(
                            101, actor_id, candidate.actors[actor_id].hp
                        )
                        current = candidate.current
                        if current.controlled:
                            candidate.end_turn(
                                current.owner_id, current.id, current.turn_count
                            )
                        else:
                            candidate.end_server_turn(current.id, candidate.turn_id)
                    else:
                        candidate.end_turn(
                            1, actor_id, candidate.actors[actor_id].turn_count
                        )
                    return candidate, []

                runtime = RuntimeMessages(fight, turn_end_provider=end)
                with self.assertRaisesRegex(ValueError, "Unsupported turn transition"):
                    runtime.end_turn(1, 100, current_wire_turn(fight))
                self.assertEqual(fight.order, old_order)
                self.assertEqual(fight.turn_id, old_turn)
                self.assertEqual(fight.actors[100].hp, 60)
                self.assertIsNone(runtime.awaiting_ack)
                self.assertEqual(runtime.pending, [])
