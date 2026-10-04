import unittest
from wakfu_server.combat_state import Actor, Fight


class EffectResolutionTests(unittest.TestCase):
    def fight(self):
        actors = [
            Actor(1, 0, (0, 0, 0), 100, 6, 3, 30, 1, 1, True),
            Actor(2, 1, (1, 0, 0), 100, 6, 3, 20, 1),
            Actor(3, 0, (2, 0, 0), 100, 6, 3, 10, 1, 1, True),
        ]
        fight = Fight(
            1,
            actors,
            {a.position for a in actors},
            {0: {actors[0].position, actors[2].position}, 1: {actors[1].position}},
        )
        fight.ready(1)
        return fight

    def test_last_enemy_death_allows_remaining_healing_then_finishes_once(self):
        fight = self.fight()
        fight.actors[1].hp = 50
        with fight.effect_resolution():
            with fight.effect_resolution():
                fight.apply_effect_damage(1, 2, 100)
            self.assertEqual(fight.phase, "active")
            fight.apply_effect_healing(1, 1, 20)
            with self.assertRaises(ValueError):
                fight.apply_effect_healing(1, 2, 20)
        self.assertEqual(
            (fight.phase, fight.winner, fight.actors[1].hp), ("finished", 0, 70)
        )
        self.assertEqual(sum(e["kind"] == "finished" for e in fight.events), 1)

    def test_current_death_advances_only_after_resolution(self):
        fight = self.fight()
        turn = fight.turn_id
        with fight.effect_resolution():
            fight.apply_effect_damage(2, 1, 100)
            self.assertEqual(fight.current.id, 1)
            self.assertEqual(fight.turn_id, turn)
        self.assertEqual(fight.current.id, 2)
        self.assertEqual(fight.turn_id, turn + 1)

    def test_both_teams_dead_finishes_without_winner_or_empty_order_crash(self):
        fight = self.fight()
        with fight.effect_resolution():
            for uid in (2, 3, 1):
                fight.apply_effect_damage(1, uid, 100)
        self.assertEqual(fight.phase, "finished")
        self.assertIsNone(fight.winner)
        self.assertEqual(fight.order, [])

    def test_resource_snapshot_tracks_spending_movement_healing_and_turn_reset(self):
        fight = self.fight()
        actor = fight.actors[1]
        actor.effect_stats = {1: 100, 2: 6, 3: 3}
        fight.spend(1, 1, ap=2)
        fight.walkable.add((0, 1, 0))
        fight.move(1, 1, [(0, 1, 0)])
        fight.apply_effect_damage(2, 1, 30)
        fight.apply_effect_healing(1, 1, 10)
        self.assertEqual(actor.effect_stats, {1: 80, 2: 4, 3: 2})
        fight._begin_turn()
        self.assertEqual(actor.effect_stats, {1: 80, 2: 6, 3: 3})
