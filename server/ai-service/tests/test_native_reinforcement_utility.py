"""Registered native reinforcements contribute bounded, configurable utility."""
from copy import deepcopy
import unittest

from test_native_target_priorities import _combat_actor, _score_root
from wakfu_ai.planning.scoring import evaluate
from wakfu_ai.planning.tactical import DEFAULT_WEIGHTS


class NativeReinforcementUtilityTests(unittest.TestCase):
    def setUp(self):
        self.root = _score_root(
            {
                1: _combat_actor(1, 1, (0, 0, 0)),
                2: _combat_actor(2, 0, (3, 0, 0)),
            }
        )
        self.summoned = deepcopy(self.root)
        self.summoned["actors"][1]["ap"] -= 3
        self.summoned["actors"][3] = _combat_actor(
            3, 1, (1, 0, 0), registered_summon=True
        )

    def score(self, state, weights=None, root=None):
        return evaluate(
            root or self.root,
            state,
            1,
            weights or dict(DEFAULT_WEIGHTS),
            {},
            summon_value=0.25,
        )

    def test_living_registered_ally_offsets_real_cast_cost(self):
        score, components, intent, target = self.score(self.summoned)
        self.assertGreater(score, 0)
        self.assertEqual(components["reinforcements"], 7.5)
        self.assertAlmostEqual(components["resources"], -0.3)
        self.assertEqual((intent, target), ("protect", None))

    def test_policy_can_disable_reinforcement_preference(self):
        weights = dict(DEFAULT_WEIGHTS, reinforcements=0)
        self.assertLess(self.score(self.summoned, weights)[0], 0)

    def test_new_enemy_reinforcement_has_negative_utility(self):
        self.summoned["actors"][3]["team"] = 0
        self.assertEqual(self.score(self.summoned)[1]["reinforcements"], -7.5)

    def test_unregistered_actor_receives_no_reinforcement_reward(self):
        self.summoned["actors"][3]["registeredSummon"] = False
        self.assertEqual(self.score(self.summoned)[1]["reinforcements"], 0)

    def test_dead_registered_actor_receives_no_reinforcement_reward(self):
        self.summoned["actors"][3]["hp"] = 0
        self.assertEqual(self.score(self.summoned)[1]["reinforcements"], 0)

    def test_existing_summon_is_not_rewarded_again(self):
        self.assertEqual(self.score(self.summoned, root=self.summoned)[0], 0)

    def test_immediate_damage_can_outweigh_reinforcement(self):
        damaged = deepcopy(self.root)
        damaged["actors"][2]["hp"] -= 15
        damaged["actors"][1]["ap"] -= 3
        self.assertGreater(self.score(damaged)[0], self.score(self.summoned)[0])


if __name__ == "__main__":
    unittest.main()
