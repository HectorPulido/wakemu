"""Current-actor KO must preserve a real timeline round boundary."""
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_timeline_snapshot import current_wire_turn


class RiftDeathRoundBoundaryTests(unittest.TestCase):
    def test_last_actor_end_reaction_preserves_round_and_rift_budget(self):
        for rift in (False, True):
            with self.subTest(rift=rift):
                actors = [
                    Actor(7, 0, (0, 0, 0), 50, 6, 3, 1000, 1, 3, True),
                    Actor(8, 0, (1, 0, 0), 50, 6, 3, 900, 1, 3, True),
                    Actor(-200, 1, (2, 0, 0), 50, 6, 3, 1, 1),
                ]
                fight = Fight(
                    734,
                    actors,
                    {a.position for a in actors},
                    {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0)}},
                )
                if rift:
                    fight.rift_wave_state = dict(
                        instance_id=8, wave=1, turn_budget=1, wave_actor_ids=[-200]
                    )
                fight.ready(3)
                self.assertEqual(fight.order[-1], 8)
                while fight.current.id != 8:
                    actor = fight.current
                    if actor.controlled:
                        fight.end_turn(actor.owner_id, actor.id, actor.turn_count)
                    else:
                        fight.end_server_turn(actor.id, fight.turn_id)
                before_round, before_turn = fight.native_timeline_round, fight.turn_id

                def lethal_end(candidate, *, actor_id, action_id):
                    candidate.apply_effect_damage(
                        7, actor_id, candidate.actors[actor_id].hp
                    )
                    return candidate, []

                runtime = RuntimeMessages(fight, turn_end_provider=lethal_end)
                runtime.end_turn(3, 8, current_wire_turn(fight))
                self.assertEqual(fight.actors[8].hp, 0)
                self.assertEqual(fight.native_timeline_round, before_round + 1)
                self.assertEqual(fight.turn_id, before_turn + 1)
                if rift:
                    self.assertEqual((fight.phase, fight.winner), ("finished", 0))
                    self.assertEqual(fight.rift_wave_state["outcome"], "survived")
                else:
                    self.assertEqual((fight.phase, fight.current.id), ("active", 7))


if __name__ == "__main__":
    unittest.main()
