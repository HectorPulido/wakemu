"""Protocol-2 tactical planner contract and search regression tests."""
import copy
import sys
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

_DIRECTORY = Path(__file__).resolve().parent
if str(_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_DIRECTORY))
import tactical
import planner
import scoring


def actor(
    identity, team, position, hp=30, *, controlled=False, ap=6, mp=3, wp=2, armor=0
):
    return {
        "id": identity,
        "team": team,
        "hp": hp,
        "max_hp": 30,
        "armor": armor,
        "controlled": controlled,
        "position": list(position),
        "mp": mp,
        "ap": ap,
        "wp": wp,
    }


def snapshot():
    cells = [[x, 0, z] for x in range(3) for z in (0, 2)]
    edges = [
        [[0, 0, 0], [1, 0, 0]],
        [[1, 0, 0], [0, 0, 0]],
        [[1, 0, 0], [2, 0, 0]],
        [[2, 0, 0], [1, 0, 0]],
        [[0, 0, 0], [1, 0, 2]],
        [[1, 0, 2], [0, 0, 0]],
    ]
    actors = [actor(-2, 1, (0, 0, 0)), actor(1, 0, (2, 0, 0), controlled=True)]
    return {
        "protocol": 2,
        "requestId": "req-1",
        "stateKey": "snapshot-key",
        "fight_id": 77,
        "actor_id": -2,
        "current_id": -2,
        "walkable": cells,
        "edges": edges,
        "actors": copy.deepcopy(actors),
        "fightInstanceId": "fight-instance-77",
        "turnId": 4,
        "stateRevision": 12,
        "catalogVersion": "catalog-9",
        "policyVersion": "policy-3",
        "rootState": "root",
        "states": [{"key": "root", "actors": copy.deepcopy(actors), "transitions": []}],
    }


def add_state(data, key, actors, transitions=None, **values):
    state = {
        "key": key,
        "actors": copy.deepcopy(actors),
        "transitions": transitions or [],
    }
    state.update(values)
    data["states"].append(state)


def transition(identity, action, destination, supported=True):
    return {
        "id": identity,
        "action": action,
        "nextState": destination,
        "supported": supported,
    }


def cast(target_id, target=(2, 0, 0), spell_id=100):
    return {
        "type": "cast",
        "spellId": spell_id,
        "level": 1,
        "targetId": target_id,
        "target": list(target),
    }


def decide(data):
    return tactical.decide(data, planner.validate)


class TacticalSearchTests(unittest.TestCase):
    def test_selects_highest_net_damage_and_reports_components(self):
        data = snapshot()
        hurt10, hurt20 = copy.deepcopy(data["actors"]), copy.deepcopy(data["actors"])
        hurt10[1]["hp"], hurt20[1]["hp"] = 20, 10
        data["states"][0]["transitions"] = [transition("hit-10", cast(1), "damaged-10")]
        add_state(
            data,
            "damaged-10",
            hurt10,
            [transition("hit-20", cast(1, spell_id=101), "damaged-20")],
        )
        add_state(data, "damaged-20", hurt20)
        result = decide(data)
        self.assertEqual(result["protocol"], 2)
        self.assertEqual(
            result["decision"]["actions"], [cast(1), cast(1, spell_id=101)]
        )
        self.assertEqual(
            (result["decision"]["intent"], result["decision"]["target_id"]),
            ("damage", 1),
        )
        self.assertEqual(result["decision"]["score_components"]["damage"], 20)
        self.assertEqual(result["decision"]["transitionIds"], ["hit-10", "hit-20"])
        for field in (
            "fightInstanceId",
            "turnId",
            "stateRevision",
            "catalogVersion",
            "policyVersion",
        ):
            self.assertEqual(result[field], data[field])

    def test_finishing_action_beats_nonlethal_damage(self):
        data = snapshot()
        hurt, killed = copy.deepcopy(data["actors"]), copy.deepcopy(data["actors"])
        hurt[1]["hp"], killed[1]["hp"] = 1, 0
        data["states"][0]["transitions"] = [transition("hurt", cast(1), "hurt")]
        add_state(
            data, "hurt", hurt, [transition("finish", cast(1, spell_id=101), "dead")]
        )
        add_state(data, "dead", killed)
        result = decide(data)
        self.assertEqual(
            (result["decision"]["intent"], result["decision"]["target_id"]),
            ("finish", 1),
        )
        self.assertEqual(result["decision"]["transitionIds"], ["hurt", "finish"])
        self.assertEqual(result["decision"]["score_components"]["kills"], 25)

    def test_healing_scores_and_selects_ally(self):
        data = snapshot()
        ally, enemy = actor(-2, 1, (0, 0, 0), 20), actor(
            1, 0, (2, 0, 0), controlled=True
        )
        data["actors"] = [ally, enemy]
        data["states"][0]["actors"] = copy.deepcopy(data["actors"])
        healed = [copy.deepcopy(ally), copy.deepcopy(enemy)]
        healed[0]["hp"] = 28
        data["states"][0]["transitions"] = [
            transition("heal-ally", cast(-2, (0, 0, 0)), "healed")
        ]
        add_state(data, "healed", healed)
        result = decide(data)
        self.assertEqual(
            (result["decision"]["intent"], result["decision"]["target_id"]),
            ("heal", -2),
        )
        self.assertEqual(result["decision"]["score_components"]["healing"], 8)

    def test_friendly_fire_loses_to_zero_score_baseline(self):
        data = snapshot()
        harmed = copy.deepcopy(data["actors"])
        harmed[0]["hp"] = 10
        data["states"][0]["transitions"] = [
            transition("friendly-fire", cast(-2, (0, 0, 0)), "harmed")
        ]
        add_state(data, "harmed", harmed)
        result = decide(data)
        self.assertEqual(result["decision"]["actions"], [{"type": "end_turn"}])
        self.assertEqual(result["decision"]["intent"], "end_turn")

    def test_threat_reduction_selects_retreat_movement(self):
        data = snapshot()
        moved = copy.deepcopy(data["actors"])
        moved[0]["position"] = [1, 0, 2]
        data["states"][0].update(
            threat=10,
            transitions=[
                transition("retreat", {"type": "move", "path": [[1, 0, 2]]}, "safer")
            ],
        )
        add_state(data, "safer", moved, threat=2)
        result = decide(data)
        self.assertEqual(result["decision"]["intent"], "retreat")
        self.assertEqual(
            result["decision"]["actions"], [{"type": "move", "path": [[1, 0, 2]]}]
        )
        self.assertEqual(result["decision"]["score_components"]["threat"], 8)

    def test_forecasted_height_edge_accepted_and_missing_edge_rejected(self):
        data = snapshot()
        moved = copy.deepcopy(data["actors"])
        moved[0]["position"] = [1, 0, 2]
        data["states"][0]["transitions"] = [
            transition("climb", {"type": "move", "path": [[1, 0, 2]]}, "upper")
        ]
        add_state(data, "upper", moved, positionValue=5)
        self.assertEqual(decide(data)["decision"]["actions"][0]["type"], "move")
        data["edges"].remove([[0, 0, 0], [1, 0, 2]])
        with self.assertRaisesRegex(ValueError, "Illegal forecast movement edge"):
            decide(data)

    def test_unsupported_transition_is_discarded_and_counted(self):
        data = snapshot()
        data["states"][0]["transitions"] = [
            {
                "id": "unknown",
                "action": {"type": "face", "direction": 2},
                "supported": False,
            }
        ]
        result = decide(data)
        self.assertEqual(result["decision"]["actions"], [{"type": "end_turn"}])
        self.assertEqual(result["trace"]["unsupportedTransitions"], 1)

    def test_supported_unknown_action_is_rejected(self):
        data = snapshot()
        data["states"][0]["transitions"] = [
            transition("face", {"type": "face", "direction": 2}, "next")
        ]
        add_state(data, "next", data["actors"])
        with self.assertRaisesRegex(ValueError, "Unsupported action type"):
            decide(data)

    def test_repeated_state_cycle_is_not_expanded(self):
        data = snapshot()
        moved = copy.deepcopy(data["actors"])
        moved[0]["position"] = [1, 0, 0]
        data["states"][0]["transitions"] = [
            transition("out", {"type": "move", "path": [[1, 0, 0]]}, "there")
        ]
        add_state(
            data,
            "there",
            moved,
            [transition("back", {"type": "move", "path": [[0, 0, 0]]}, "root")],
        )
        result = decide(data)
        self.assertEqual(result["trace"]["expanded"], 1)
        self.assertEqual(result["decision"]["actions"], [{"type": "end_turn"}])

    def test_root_mismatch_checkpoint_and_policy_rejected(self):
        data = snapshot()
        data["states"][0]["actors"][0]["wp"] -= 1
        with self.assertRaisesRegex(ValueError, "root context differs from snapshot"):
            decide(data)
        data = snapshot()
        data["teamContext"] = {
            "fightInstanceId": "another-fight",
            "stateRevision": 12,
            "team": 1,
            "focusId": None,
            "reservedCells": [],
        }
        with self.assertRaisesRegex(ValueError, "Stale or foreign team checkpoint"):
            decide(data)
        data = snapshot()
        data["policy"] = {"weights": {"damage": -1}}
        with self.assertRaisesRegex(ValueError, "Invalid weight damage"):
            decide(data)

    def test_planner_dispatches_v2_and_rejects_unknown_protocol(self):
        self.assertEqual(planner.decide(snapshot())["protocol"], 2)
        data = snapshot()
        data["protocol"] = 3
        with self.assertRaises(ValueError):
            planner.decide(data)

    def test_unweighted_outcome_feature_is_ignored_and_weighted_feature_is_ranked(self):
        data = snapshot()
        after = copy.deepcopy(data["actors"])
        data["states"][0]["transitions"] = [transition("glyph", cast(1), "controlled")]
        add_state(data, "controlled", after, outcomeFeatures={"glyph_control": 10})

        unweighted = decide(data)
        self.assertEqual(unweighted["decision"]["actions"], [{"type": "end_turn"}])

        data["policy"] = {"featureWeights": {"glyph_control": 2}}
        weighted = decide(data)
        self.assertEqual(weighted["decision"]["actions"], [cast(1)])
        self.assertEqual(
            weighted["decision"]["score_components"]["feature:glyph_control"], 20
        )

    def test_invalid_feature_name_and_nonfinite_weight_are_rejected(self):
        data = snapshot()
        data["policy"] = {"featureWeights": {"Glyph Control": 2}}
        with self.assertRaisesRegex(ValueError, "Invalid feature name"):
            decide(data)
        data = snapshot()
        data["policy"] = {"featureWeights": {"glyph_control": float("nan")}}
        with self.assertRaisesRegex(ValueError, "Invalid feature weights"):
            decide(data)

    def test_search_is_reproducible_under_concurrent_requests(self):
        data = snapshot()
        hurt = copy.deepcopy(data["actors"])
        hurt[1]["hp"] = 15
        data["states"][0]["transitions"] = [transition("hit", cast(1), "hurt")]
        add_state(data, "hurt", hurt)
        expected = planner.decide(data)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(
                pool.map(lambda _: planner.decide(copy.deepcopy(data)), range(32))
            )
        stable = lambda result: (
            result["decision"],
            result["trace"]["expanded"],
            result["trace"]["alternatives"],
        )
        self.assertTrue(all(stable(result) == stable(expected) for result in results))

    def test_node_and_depth_limits_bound_search(self):
        data = snapshot()
        hurt10, hurt20 = copy.deepcopy(data["actors"]), copy.deepcopy(data["actors"])
        hurt10[1]["hp"], hurt20[1]["hp"] = 20, 10
        data["states"][0]["transitions"] = [transition("hit-10", cast(1), "damaged-10")]
        add_state(
            data,
            "damaged-10",
            hurt10,
            [transition("hit-20", cast(1, spell_id=101), "damaged-20")],
        )
        add_state(data, "damaged-20", hurt20)

        node_limited = copy.deepcopy(data)
        node_limited["policy"] = {"nodes": 1}
        result = decide(node_limited)
        self.assertEqual(result["trace"]["expanded"], 1)
        self.assertTrue(result["trace"]["nodeLimitReached"])

        depth_limited = copy.deepcopy(data)
        depth_limited["policy"] = {"depth": 1}
        result = decide(depth_limited)
        self.assertEqual(result["decision"]["transitionIds"], ["hit-10"])
        self.assertEqual(result["trace"]["expanded"], 1)


class CapabilityContractTests(unittest.TestCase):
    def test_tactical_large_native_arena_preserves_legacy_limits(self):
        data = snapshot()
        data["walkable"] += [[x, 2, 0] for x in range(9000)]
        result_actors = copy.deepcopy(data["actors"])
        result_actors[1]["hp"] -= 5
        add_state(data, "hit", result_actors)
        data["states"][0]["transitions"] = [transition("hit", cast(1), "hit")]
        self.assertEqual(planner.decide(data)["decision"]["intent"], "damage")
        with self.assertRaises(ValueError):
            planner.decide(dict(data, protocol=1))
        data["walkable"] += [[x, 3, 0] for x in range(32768)]
        with self.assertRaises(ValueError):
            planner.decide(data)

    def test_mixed_capabilities_are_advisory_and_nonexclusive(self):
        data = snapshot()
        baseline = decide(copy.deepcopy(data))["decision"]
        data["capabilities"] = [
            dict(
                spellId=100,
                level=1,
                minimum=0,
                maximum=4,
                tags=["damage", "heal", "control", "summon"],
            )
        ]
        result = decide(data)
        self.assertEqual(result["decision"], baseline)
        self.assertEqual(
            result["trace"]["roleAffinities"],
            dict(melee=0, ranged=1, support=1, controller=1, summoner=1, unknown=0),
        )

    def test_malformed_or_duplicate_capabilities_are_rejected(self):
        entry = dict(spellId=100, level=1, minimum=0, maximum=4, tags=["damage"])
        for entries in (
            [dict(entry, spellId=True)],
            [dict(entry, minimum=5)],
            [dict(entry, tags=[])],
            [dict(entry, conditional=1)],
            [entry, entry],
        ):
            with self.subTest(entries=entries):
                data = snapshot()
                data["capabilities"] = entries
                with self.assertRaises(ValueError):
                    decide(data)


class ExplicitForecastCorpusTests(unittest.TestCase):
    """Synthetic forecast deltas test planner ranking, not native spell support."""

    def test_area_damage_scores_multiple_enemies_and_ally_damage_net(self):
        data = snapshot()
        cells = [[x, 0, 0] for x in range(6)]
        actors = [
            actor(-2, 1, (0, 0, 0)),
            actor(-3, 1, (1, 0, 0), hp=20),
            actor(1, 0, (3, 0, 0), controlled=True),
            actor(2, 0, (4, 0, 0), controlled=True),
        ]
        data.update(walkable=cells, edges=[], actors=copy.deepcopy(actors))
        data["states"][0] = {
            "key": "root",
            "actors": copy.deepcopy(actors),
            "transitions": [],
        }
        after = copy.deepcopy(actors)
        after[1]["hp"] = 15
        after[2]["hp"] = 20
        after[3]["hp"] = 25
        action = {"type": "cast", "spellId": 900, "level": 1, "target": [2, 0, 0]}
        data["states"][0]["transitions"] = [transition("area", action, "area-result")]
        add_state(data, "area-result", after)

        result = decide(data)

        self.assertEqual(result["decision"]["actions"], [action])
        self.assertEqual(result["decision"]["score_components"]["damage"], 15)
        self.assertEqual(result["decision"]["score_components"]["healing"], -5)
        self.assertEqual(result["decision"]["score"], 10)
        self.assertEqual(result["decision"]["intent"], "damage")

    def test_zero_effect_attack_loses_to_useful_attack(self):
        data = snapshot()
        immune = copy.deepcopy(data["actors"])
        immune[0]["ap"] -= 1
        useful = copy.deepcopy(data["actors"])
        useful[0]["ap"] -= 1
        useful[1]["hp"] -= 5
        data["states"][0]["transitions"] = [
            transition("immune-hit", cast(1, spell_id=100), "immune"),
            transition("useful-hit", cast(1, spell_id=101), "useful"),
        ]
        add_state(data, "immune", immune)
        add_state(data, "useful", useful)

        result = decide(data)

        self.assertEqual(result["decision"]["actions"], [cast(1, spell_id=101)])
        self.assertEqual(result["decision"]["score_components"]["damage"], 5)

    def test_reflect_killing_npc_loses_even_when_target_takes_damage(self):
        data = snapshot()
        reflected = copy.deepcopy(data["actors"])
        reflected[0]["hp"] = 0
        reflected[0]["ap"] -= 1
        reflected[1]["hp"] -= 10
        safe = copy.deepcopy(data["actors"])
        safe[0]["ap"] -= 1
        safe[1]["hp"] -= 4
        data["states"][0]["transitions"] = [
            transition("reflect", cast(1, spell_id=100), "reflected"),
            transition("safe-hit", cast(1, spell_id=101), "safe"),
        ]
        add_state(data, "reflected", reflected)
        add_state(data, "safe", safe)

        result = decide(data)

        self.assertEqual(result["decision"]["actions"], [cast(1, spell_id=101)])
        self.assertEqual(result["decision"]["score_components"]["damage"], 4)
        self.assertNotEqual(result["decision"]["transitionIds"], ["reflect"])
        actor_id, states, weights, _, team, _, feature_weights = tactical.validate(
            data, planner.validate
        )
        reflected_score, reflected_components, _, _ = scoring.evaluate(
            states["root"],
            states["reflected"],
            actor_id,
            weights,
            team,
            feature_weights,
        )
        self.assertLess(reflected_score, 0)
        self.assertEqual(reflected_components["healing"], -30)
        self.assertEqual(reflected_components["kills"], -25)

    def test_certified_threat_reduction_can_beat_risk_free_kill_by_profile(self):
        data = snapshot()
        data["states"][0]["threat"] = 10
        killed = copy.deepcopy(data["actors"])
        killed[0]["ap"] -= 1
        killed[1]["hp"] = 0
        retreat = copy.deepcopy(data["actors"])
        retreat[0]["position"] = [1, 0, 0]
        retreat[0]["mp"] -= 1
        data["states"][0]["transitions"] = [
            transition("finish", cast(1), "killed"),
            transition("withdraw", {"type": "move", "path": [[1, 0, 0]]}, "safer"),
        ]
        add_state(data, "killed", killed, threat=10)
        add_state(data, "safer", retreat, threat=0)
        data["policy"] = {"weights": {"damage": 0, "kills": 0, "threat": 2}}

        result = decide(data)

        self.assertEqual(
            result["decision"]["actions"], [{"type": "move", "path": [[1, 0, 0]]}]
        )
        self.assertEqual(result["decision"]["intent"], "retreat")
        self.assertEqual(result["decision"]["score_components"]["threat"], 20)

    def test_planned_sequence_consumes_world_forecast_ap_and_wp_deltas(self):
        data = snapshot()
        first = copy.deepcopy(data["actors"])
        first[0]["ap"] -= 3
        first[0]["wp"] -= 1
        first[1]["hp"] -= 6
        final = copy.deepcopy(first)
        final[0]["ap"] -= 3
        final[0]["wp"] -= 1
        final[1]["hp"] -= 6
        first_action = cast(1, spell_id=100)
        second_action = cast(1, spell_id=101)
        data["states"][0]["transitions"] = [
            transition("costly-first", first_action, "after-first")
        ]
        add_state(
            data,
            "after-first",
            first,
            [transition("costly-second", second_action, "after-second")],
        )
        add_state(data, "after-second", final)

        result = decide(data)

        self.assertEqual(result["decision"]["actions"], [first_action, second_action])
        self.assertEqual(
            result["decision"]["transitionIds"], ["costly-first", "costly-second"]
        )
        self.assertEqual(result["decision"]["score_components"]["damage"], 12)
        # Resource values are deltas from the common root forecast.
        self.assertEqual(result["decision"]["score_components"]["resources"], -0.8)

    def test_two_fight_uuids_are_echoed_without_cross_request_state(self):
        first, second = snapshot(), snapshot()
        first.update(
            requestId="request-A", fightInstanceId="fight-A", stateKey="state-A"
        )
        second.update(
            requestId="request-B", fightInstanceId="fight-B", stateKey="state-B"
        )
        hurt = copy.deepcopy(first["actors"])
        hurt[1]["hp"] -= 7
        first["states"][0]["transitions"] = [transition("hit-A", cast(1), "hurt-A")]
        add_state(first, "hurt-A", hurt)
        second["states"][0]["transitions"] = []

        with ThreadPoolExecutor(max_workers=2) as pool:
            response_a, response_b = list(pool.map(planner.decide, (first, second)))

        self.assertEqual(
            (
                response_a["requestId"],
                response_a["fightInstanceId"],
                response_a["stateKey"],
            ),
            ("request-A", "fight-A", "state-A"),
        )
        self.assertEqual(
            (
                response_b["requestId"],
                response_b["fightInstanceId"],
                response_b["stateKey"],
            ),
            ("request-B", "fight-B", "state-B"),
        )
        self.assertEqual(response_a["decision"]["actions"], [cast(1)])
        self.assertEqual(response_b["decision"]["actions"], [{"type": "end_turn"}])


if __name__ == "__main__":
    unittest.main()
