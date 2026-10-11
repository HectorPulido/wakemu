"""Real generic timeline boundary for configured local boss survival."""
import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.maps.boss_score_runtime import install
from wakfu_server.maps.boss_score import POLICY


class BossScoreTimelineTests(unittest.TestCase):
    def test_twenty_complete_rounds_finish_with_living_boss(self):
        actors = [
            Actor(1, 0, (0, 0, 0), 20, 6, 3, 100, 1, 1, True),
            Actor(-1, 1, (2, 0, 0), 10, 6, 3, 50, 1),
        ]
        fight = Fight(
            7, actors, {(x, 0, 0) for x in range(3)}, {0: {(0, 0, 0)}, 1: {(2, 0, 0)}}
        )
        install(
            fight,
            dict(
                policy=POLICY,
                bosses={"-1": {"reference": 4378}},
                player_ids=[1],
                player_team=0,
                round_limit=20,
            ),
        )
        fight.ready(1)
        for round_number in range(1, 21):
            self.assertEqual("active", fight.phase)
            fight.end_turn(1, 1, fight.actors[1].turn_count)
            self.assertEqual("active", fight.phase)
            fight.end_server_turn(-1, fight.turn_id)
            self.assertEqual(
                "finished" if round_number == 20 else "active", fight.phase
            )
        self.assertEqual(0, fight.winner)
        self.assertEqual(10, fight.actors[-1].hp)
        self.assertEqual(21, fight.native_timeline_round)
