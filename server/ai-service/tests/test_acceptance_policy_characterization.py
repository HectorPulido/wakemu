"""Characterize current utility gaps reported during low-level mob acceptance.

These are policy observations, not replacements for existing expectations or
native combat proofs. No native catalog, world service or database is loaded.
"""
from copy import deepcopy
import unittest
from unittest.mock import patch

from wakfu_ai.planning.query_search import _metrics
from wakfu_ai.planning.scoring import evaluate
from wakfu_ai.planning.tactical import DEFAULT_WEIGHTS


def actor(identity, team, x, hp=100):
    return dict(
        id=identity,
        team=team,
        position=[x, 0, 0],
        hp=hp,
        max_hp=100,
        armor=0,
        ap=6,
        mp=3,
        wp=0,
    )


class AcceptancePolicyCharacterizationTests(unittest.TestCase):
    def score(self, before, after):
        return evaluate(
            _metrics(before, 1), _metrics(after, 1), 1, DEFAULT_WEIGHTS, {}
        )[0]

    def test_generic_position_rewards_approach_after_equal_damage(self):
        root = dict(actors=[actor(1, 1, 0), actor(2, 2, 3)])
        melee = deepcopy(root)
        melee["actors"][0]["position"] = [2, 0, 0]
        melee["actors"][0]["mp"] = 1
        melee["actors"][1]["hp"] = 80
        retreat = deepcopy(melee)
        retreat["actors"][0]["position"] = [0, 0, 0]
        retreat["actors"][0]["mp"] = 0
        self.assertGreater(self.score(root, melee), self.score(root, retreat))
        self.assertEqual(_metrics(melee, 1)["threat"], 0)

    def test_summon_and_player_damage_have_equal_utility_without_focus(self):
        root = dict(actors=[actor(1, 1, 0), actor(2, 2, 3), actor(3, 2, 3)])
        root["actors"][2]["is_summon"] = True
        root["actors"][2]["owner_id"] = 2
        player_hit, summon_hit = deepcopy(root), deepcopy(root)
        player_hit["actors"][1]["hp"] -= 20
        summon_hit["actors"][2]["hp"] -= 20
        self.assertEqual(self.score(root, player_hit), self.score(root, summon_hit))

    def test_unweighted_hazard_feature_has_no_utility_penalty(self):
        root = dict(
            actors=[actor(1, 1, 0), actor(2, 2, 3)],
            outcomeFeatures={"hazard_exposure": 0},
        )
        safe, hazardous = deepcopy(root), deepcopy(root)
        hazardous["outcomeFeatures"]["hazard_exposure"] = 1
        self.assertEqual(self.score(root, safe), self.score(root, hazardous))


class EqualOutcomeTargetOrderingTests(unittest.TestCase):
    def test_equal_area_outcomes_keep_first_candidate_even_when_target_is_empty(self):
        from test_query_search import fixture, run_search, ENEMY_ID

        occupied = dict(
            type="cast", spellId=701, level=1, target=[3, 0, 0], targetId=ENEMY_ID
        )
        empty = dict(occupied, target=[2, 0, 0], targetId=None)
        for first, second in ((empty, occupied), (occupied, empty)):
            with self.subTest(first_target=first["targetId"]):
                session = fixture([], effects={701: "damage"}, edges=[])
                session.envelope["policy"]["limits"]["depth"] = 1
                original = session.request

                def same_area_outcome(query):
                    query = deepcopy(query)
                    if query["operation"] == "preview":
                        query["action"]["targetId"] = ENEMY_ID
                    return original(query)

                session.request = same_area_outcome
                with patch(
                    "wakfu_ai.planning.query_search.candidates",
                    return_value=iter([first, second]),
                ):
                    result = run_search(session)
                self.assertEqual(result["action"], first)


class ForecastNoisePlanCharacterizationTests(unittest.TestCase):
    def test_no_effect_prefix_can_win_when_next_damage_sample_is_larger(self):
        from test_query_search import fixture, run_search, ACTOR_ID, ENEMY_ID

        session = fixture([], effects={701: "damage"}, edges=[])
        session.envelope["policy"]["limits"]["depth"] = 2
        original = session.request

        def sampled(query):
            if query["operation"] != "preview":
                return original(query)
            previous = session.states[query["state"]]["public"]
            before = next(a for a in previous["actors"] if a["id"] == ACTOR_ID)
            enemy = next(a for a in previous["actors"] if a["id"] == ENEMY_ID)
            result = original(query)
            state = result["result"]
            acting = next(a for a in state["actors"] if a["id"] == ACTOR_ID)
            victim = next(a for a in state["actors"] if a["id"] == ENEMY_ID)
            acting["ap"] = before["ap"] - 3
            if query["action"]["targetId"] == ENEMY_ID:
                victim["hp"] = enemy["hp"] - (6 if before["ap"] == 3 else 5)
            return result

        session.request = sampled
        occupied = dict(
            type="cast", spellId=701, level=1, target=[3, 0, 0], targetId=ENEMY_ID
        )
        empty = dict(occupied, target=[2, 0, 0], targetId=None)

        def choices(graph, state, repertoire, actor_id, *args, **kwargs):
            actor = next(a for a in state["actors"] if a["id"] == ACTOR_ID)
            enemy = next(a for a in state["actors"] if a["id"] == ENEMY_ID)
            if actor["ap"] >= 3 and enemy["hp"] == 30:
                yield from (empty, occupied)

        with patch("wakfu_ai.planning.query_search.candidates", side_effect=choices):
            result = run_search(session)
        self.assertEqual(result["action"], empty)
        self.assertEqual(result["components"]["damage"], 6)


if __name__ == "__main__":
    unittest.main()
