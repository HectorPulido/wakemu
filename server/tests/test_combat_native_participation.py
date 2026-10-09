"""Turn reconciliation follows native fighter membership independently of HP."""
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
    unregister_global_fighter,
)


class NativeParticipationTests(unittest.TestCase):
    def fight(self):
        fight = Fight(
            7,
            [
                Actor(100, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(200, 1, (3, 0, 0), 20, 4, 2, 20, 1),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0)}, 1: {(3, 0, 0)}},
        )
        initialize_global_pv_collections(fight, (100, 200))
        fight.ready(1)
        return fight

    def test_zero_hp_in_play_preserves_teams_control_and_round_order(self):
        fight = self.fight()
        for actor in fight.actors.values():
            actor.hp = 0
        with fight.effect_resolution():
            pass
        self.assertEqual(fight.phase, "active")
        self.assertEqual(fight.order, [100, 200])
        self.assertIsNone(fight.winner)
        fight.spend(1, 100, ap=1)
        self.assertEqual(fight.actors[100].ap, 5)
        fight.native_base_turn_order = [100, 200]
        fight.end_turn(1, 100, 1)
        self.assertEqual(fight.current.id, 200)
        fight.end_server_turn(200, 2)
        self.assertEqual(fight.current.id, 100)
        self.assertEqual(fight.order, [100, 200])

    def test_off_play_positive_hp_is_not_a_participating_team(self):
        fight = self.fight()
        set_global_fighter_status(fight, 200, "OFF_PLAY")
        fight._settle_deaths()
        self.assertEqual(fight.order, [100])
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))

    def test_attested_retirement_excludes_actor_retained_in_checkpoint(self):
        fight = self.fight()
        unregister_global_fighter(fight, 200)
        fight._settle_deaths()
        self.assertEqual(fight.order, [100])
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))

    def test_missing_native_status_rejects_before_reconciliation_mutation(self):
        fight = self.fight()
        del fight.native_global_pv_collections["fighter_status"]["200"]
        before = (
            tuple(fight.order),
            fight.phase,
            fight.winner,
            fight.turn_index,
            tuple(fight.events),
        )
        with self.assertRaisesRegex(ValueError, "native fighter status"):
            fight._settle_deaths()
        self.assertEqual(
            before,
            (
                tuple(fight.order),
                fight.phase,
                fight.winner,
                fight.turn_index,
                tuple(fight.events),
            ),
        )


if __name__ == "__main__":
    unittest.main()
