"""Outcome-policy guardrails for evaluating foreign tactical heuristics.

These use already-authoritative outcomes, not a second combat simulator. Damage,
overkill and overheal must be resolved by the native executor before scoring.
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

_SERVICE = Path(__file__).resolve().parents[1]
if str(_SERVICE) not in sys.path:
    sys.path.insert(0, str(_SERVICE))

from wakfu_ai.planning.scoring import evaluate
from wakfu_ai.planning.tactical import DEFAULT_WEIGHTS


def actor(identity, team, hp=100, *, maximum=100, registered=False):
    result = dict(
        id=identity,
        team=team,
        hp=hp,
        max_hp=maximum,
        armor=0,
        ap=6,
        mp=3,
        wp=2,
        position=(identity, 0, 0),
    )
    if registered:
        result["registeredSummon"] = True
    return result


def state(*actors):
    return dict(
        actors={a["id"]: a for a in actors},
        position=0,
        threat=0,
        uncertainty=0,
        features={},
    )


class OutcomePreferenceTests(unittest.TestCase):
    def score(self, root, outcome, *, team=None):
        return evaluate(
            root, outcome, 1, DEFAULT_WEIGHTS, team or {}, summon_value=0.25
        )

    def test_finish_beats_slightly_more_damage_without_foreign_max_hp_bonus(self):
        root = state(actor(1, 1), actor(2, 2, 10), actor(3, 2))
        finish, damage = deepcopy(root), deepcopy(root)
        finish["actors"][2]["hp"] = 0
        damage["actors"][3]["hp"] -= 20
        self.assertEqual(self.score(root, finish)[0], 35)
        self.assertGreater(self.score(root, finish)[0], self.score(root, damage)[0])
        self.assertEqual(self.score(root, finish)[2:], ("finish", 2))

    def test_equal_nonlethal_damage_is_not_inflated_by_preexisting_wounds(self):
        root = state(actor(1, 1), actor(2, 2, 20), actor(3, 2))
        wounded, healthy = deepcopy(root), deepcopy(root)
        wounded["actors"][2]["hp"] -= 5
        healthy["actors"][3]["hp"] -= 5
        self.assertEqual(self.score(root, wounded)[0], self.score(root, healthy)[0])

    def test_larger_area_outcome_beats_small_hit_on_wounded_enemy(self):
        root = state(actor(1, 1), actor(2, 2, 20), actor(3, 2), actor(4, 2))
        wounded, area = deepcopy(root), deepcopy(root)
        wounded["actors"][2]["hp"] -= 10
        area["actors"][3]["hp"] -= 6
        area["actors"][4]["hp"] -= 6
        self.assertGreater(self.score(root, area)[0], self.score(root, wounded)[0])

    def test_overkill_has_no_extra_reward_and_cheaper_finish_wins(self):
        root = state(actor(1, 1), actor(2, 2, 4))
        cheap, expensive = deepcopy(root), deepcopy(root)
        for outcome, ap in ((cheap, 4), (expensive, 1)):
            outcome["actors"][2]["hp"] = 0
            outcome["actors"][1]["ap"] = ap
        self.assertEqual(self.score(root, cheap)[1]["damage"], 4)
        self.assertGreater(self.score(root, cheap)[0], self.score(root, expensive)[0])

    def test_native_lifesteal_rewards_real_heal_as_well_as_damage(self):
        root = state(actor(1, 1, 30), actor(2, 2))
        plain, leech = deepcopy(root), deepcopy(root)
        plain["actors"][2]["hp"] -= 10
        leech["actors"][2]["hp"] -= 10
        leech["actors"][1]["hp"] += 5
        self.assertEqual(self.score(root, leech)[1]["healing"], 5)
        self.assertGreater(self.score(root, leech)[0], self.score(root, plain)[0])

    def test_full_health_lifesteal_has_no_phantom_heal_reward(self):
        root = state(actor(1, 1), actor(2, 2))
        plain, capped_leech = deepcopy(root), deepcopy(root)
        plain["actors"][2]["hp"] -= 10
        capped_leech["actors"][2]["hp"] -= 10
        self.assertEqual(self.score(root, plain)[0], self.score(root, capped_leech)[0])

    def test_overheal_is_not_rewarded_beyond_native_restored_health(self):
        root = state(actor(1, 1, 98), actor(2, 2))
        capped = deepcopy(root)
        capped["actors"][1]["hp"] = 100
        self.assertEqual(self.score(root, capped)[1]["healing"], 2)

    def test_friendly_fire_can_outweigh_larger_enemy_damage(self):
        root = state(actor(1, 1), actor(2, 2), actor(3, 1))
        safe, reckless = deepcopy(root), deepcopy(root)
        safe["actors"][2]["hp"] -= 10
        reckless["actors"][2]["hp"] -= 15
        reckless["actors"][3]["hp"] -= 10
        self.assertGreater(self.score(root, safe)[0], self.score(root, reckless)[0])

    def test_final_outcome_not_damage_per_ap_selects_larger_useful_turn(self):
        root = state(actor(1, 1), actor(2, 2))
        efficient, larger = deepcopy(root), deepcopy(root)
        efficient["actors"][1]["ap"] -= 1
        efficient["actors"][2]["hp"] -= 5
        larger["actors"][1]["ap"] -= 6
        larger["actors"][2]["hp"] -= 20
        self.assertGreater(self.score(root, larger)[0], self.score(root, efficient)[0])

    def test_preparation_does_not_reward_intermediate_resource_gains_twice(self):
        root = state(actor(1, 1), actor(2, 2))
        prepared, plain = deepcopy(root), deepcopy(root)
        for outcome in (prepared, plain):
            outcome["actors"][2]["hp"] -= 10
            outcome["actors"][1]["ap"] = 3
        self.assertEqual(self.score(root, prepared)[0], self.score(root, plain)[0])
        self.assertEqual(self.score(root, prepared)[1]["resources"], -0.3)

    def test_higher_victim_max_hp_does_not_multiply_finish_reward(self):
        root = state(actor(1, 1), actor(2, 2, 10, maximum=10000), actor(3, 2, 10))
        boss, ordinary = deepcopy(root), deepcopy(root)
        boss["actors"][2]["hp"] = 0
        ordinary["actors"][3]["hp"] = 0
        self.assertEqual(self.score(root, boss)[0], self.score(root, ordinary)[0])

    def test_focus_is_soft_preference_and_cannot_hide_larger_outcome(self):
        root = state(actor(1, 1), actor(2, 2), actor(3, 2))
        focused, other = deepcopy(root), deepcopy(root)
        focused["actors"][2]["hp"] -= 10
        other["actors"][3]["hp"] -= 12
        team = {"focusId": 2}
        self.assertEqual(self.score(root, focused, team=team)[1]["coordination"], 0.5)
        self.assertGreater(
            self.score(root, other, team=team)[0],
            self.score(root, focused, team=team)[0],
        )

    def test_new_certified_reinforcement_is_not_synthetic_resource_gain(self):
        root = state(actor(1, 1), actor(2, 2))
        summoned = deepcopy(root)
        summoned["actors"][1]["ap"] -= 3
        summoned["actors"][3] = actor(3, 1, 20, registered=True)
        score, parts, _, _ = self.score(root, summoned)
        self.assertEqual(parts["reinforcements"], 5)
        self.assertEqual(parts["resources"], -0.3)
        self.assertEqual(score, 4.7)
        self.assertEqual(self.score(summoned, summoned)[0], 0)

    def test_damage_then_healing_only_rewards_net_outcome(self):
        root = state(actor(1, 1), actor(2, 2, 70))
        intermediate, final = deepcopy(root), deepcopy(root)
        intermediate["actors"][2]["hp"] = 30
        final["actors"][2]["hp"] = 60
        self.assertEqual(self.score(root, intermediate)[1]["damage"], 40)
        self.assertEqual(self.score(root, final)[1]["damage"], 10)


if __name__ == "__main__":
    unittest.main()
