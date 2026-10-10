import copy
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.rift_combat_adapter import acknowledge_wave


class RiftCombatAdapterTests(unittest.TestCase):
    def fight(self, *, rift=True, turn_budget=40):
        actors = [
            Actor(1, 0, (0, 0, 0), 20, 6, 3, 100, 1, 1, True),
            Actor(-1, 1, (2, 0, 0), 10, 6, 3, 50, 1),
        ]
        fight = Fight(
            7, actors, {(x, 0, 0) for x in range(3)}, {0: {(0, 0, 0)}, 1: {(2, 0, 0)}}
        )
        if rift:
            fight.rift_wave_state = dict(
                instance_id=9, wave=1, turn_budget=turn_budget, wave_actor_ids=[-1]
            )
        fight.ready(1)
        return fight

    def test_normal_fight_still_finishes_on_last_enemy(self):
        fight = self.fight(rift=False)
        fight.apply_damage(1, -1, 10)
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))

    def test_wave_clear_keeps_same_fight_and_stages_once_without_reward(self):
        fight = self.fight()
        fight.apply_damage(1, -1, 10)
        self.assertEqual((fight.id, fight.phase, fight.winner), (7, "active", None))
        self.assertEqual(fight.current.id, 1)
        self.assertEqual(fight.order, [1])
        fight._settle_deaths()
        self.assertEqual(
            len([e for e in fight.events if e["kind"] == "rift_wave_cleared"]), 1
        )
        self.assertFalse(any(e["kind"] == "finished" for e in fight.events))
        self.assertEqual(
            fight.rift_wave_state["pending_wave"],
            dict(completed_wave=1, actor_ids=[-1], turn=1),
        )
        self.assertEqual(snapshot(fight)["rift_wave_state"]["wave"], 1)

    def test_speculative_clone_stages_no_canonical_progress(self):
        fight = self.fight()
        preview = copy.deepcopy(fight)
        preview.apply_damage(1, -1, 10)
        self.assertNotIn("pending_wave", fight.rift_wave_state)
        self.assertEqual(fight.actors[-1].hp, 10)

    def test_player_defeat_never_defers_or_spawns_wave(self):
        fight = self.fight()
        fight.end_turn(1, 1, 1)
        fight.apply_damage(-1, 1, 20)
        self.assertEqual((fight.phase, fight.winner), ("finished", 1))
        self.assertNotIn("pending_wave", fight.rift_wave_state)

    def test_survival_finishes_after_full_budget_not_early(self):
        fight = self.fight(turn_budget=1)
        fight.end_turn(1, 1, 1)
        self.assertEqual(fight.phase, "active")
        fight.end_server_turn(-1, fight.turn_id)
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))
        self.assertEqual(fight.rift_wave_state["outcome"], "survived")
        self.assertEqual(fight.actors[-1].hp, 10)

    def test_invalid_rift_policy_fails_closed(self):
        fight = self.fight()
        fight.rift_wave_state["turn_budget"] = False
        with self.assertRaisesRegex(ValueError, "frozen rift"):
            fight.apply_damage(1, -1, 10)

    def test_missing_native_admission_authority_is_rejected(self):
        fight = self.fight()
        fight.apply_damage(1, -1, 10)
        before = copy.deepcopy(fight.rift_wave_state)
        with self.assertRaises(ValueError):
            acknowledge_wave(fight, [-2], {-2: (12608, b"x")}, species_refs=[4])
        self.assertEqual(fight.rift_wave_state, before)


if __name__ == "__main__":
    unittest.main()
