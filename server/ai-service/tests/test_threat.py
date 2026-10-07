"""Contract tests for certified and approximate rival response forecasts."""
import copy
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wakfu_ai.planning import planner
from wakfu_ai.planning import tactical
from test_tactical import actor, snapshot, add_state, transition, cast


def roster_hit(actors, identity=-2, damage=5):
    result = copy.deepcopy(actors)
    result[next(i for i, a in enumerate(result) if a["id"] == identity)]["hp"] -= damage
    return result


def forecast(
    actors, *, rival=1, plans=None, mode="native", unknown=None, root_actors=None
):
    value = {"actorId": rival, "mode": mode, "plans": plans or []}
    if unknown is not None:
        value["unknownDependencies"] = unknown
    if root_actors is not None:
        value["rootActors"] = copy.deepcopy(root_actors)
    return value


def response_plan(actors, plan_id="hit", *, action=None, supported=True):
    target = next(a["position"] for a in actors if a["id"] == -2)
    action = action or cast(-2, tuple(target), spell_id=900)
    return {
        "id": plan_id,
        "supported": supported,
        "steps": [{"action": action, "actors": copy.deepcopy(actors)}],
    }


def set_forecasts(data, root_forecasts, state_forecasts=None):
    data["states"][0]["rivalForecasts"] = copy.deepcopy(root_forecasts)
    if state_forecasts is not None:
        for state in data["states"][1:]:
            state["rivalForecasts"] = copy.deepcopy(state_forecasts)


class RivalForecastTests(unittest.TestCase):
    def test_rival_risk_selects_retreat_over_risk_free_kill(self):
        data = snapshot()
        # A second rival remains alive after the risk-free kill, so withdrawing
        # must actually reduce a certified future threat.
        extra = actor(2, 0, (2, 0, 2), controlled=True)
        data["actors"].append(extra)
        data["states"][0]["actors"].append(copy.deepcopy(extra))
        data["policy"] = {"weights": {"damage": 0, "kills": 0, "threat": 2}}
        enemy_hurt = roster_hit(data["actors"], damage=10)
        moved = copy.deepcopy(data["actors"])
        moved[0]["position"] = [1, 0, 0]
        killed = copy.deepcopy(data["actors"])
        killed[1]["hp"] = 0
        data["states"][0]["transitions"] = [
            transition("finish", cast(1), "killed"),
            transition("withdraw", {"type": "move", "path": [[1, 0, 0]]}, "safer"),
        ]
        add_state(data, "killed", killed)
        add_state(data, "safer", moved)
        # Risk comes from rival 2, which remains alive after the kill of rival 1.
        root = [forecast(data["actors"], rival=2, plans=[response_plan(enemy_hurt)])]
        safer = [
            forecast(moved, rival=2, plans=[response_plan(roster_hit(moved, damage=1))])
        ]
        data["states"][1]["rivalForecasts"] = copy.deepcopy(root)
        data["states"][2]["rivalForecasts"] = safer
        data["states"][0]["rivalForecasts"] = root

        result = planner.decide(data)

        self.assertEqual(
            result["decision"]["actions"], [{"type": "move", "path": [[1, 0, 0]]}]
        )
        self.assertEqual(result["decision"]["intent"], "retreat")
        self.assertEqual(result["trace"]["rivalResponses"]["root"][0]["risk"], 10)
        self.assertEqual(result["trace"]["rivalResponses"]["selected"][0]["risk"], 1)

    def test_alternative_plans_are_maxed_not_summed_and_unsupported_is_ignored(self):
        data = snapshot()
        light, heavy = roster_hit(data["actors"], damage=5), roster_hit(
            data["actors"], damage=8
        )
        impossible = roster_hit(data["actors"], damage=25)
        plans = [
            response_plan(light, "light"),
            response_plan(heavy, "heavy"),
            response_plan(impossible, "unsupported", supported=False),
        ]
        data["states"][0]["rivalForecasts"] = [forecast(data["actors"], plans=plans)]
        result = planner.decide(data)
        detail = result["trace"]["rivalResponses"]["root"][0]
        self.assertEqual(
            (detail["risk"], detail["planId"], detail["unsupportedPlans"]),
            (8, "heavy", 1),
        )
        self.assertEqual(result["decision"]["actions"], [{"type": "end_turn"}])

    def test_friendly_fire_offsets_enemy_healing_for_best_response(self):
        data = snapshot()
        data["actors"][1]["hp"] = 20
        data["actors"][1]["max_hp"] = 50
        data["states"][0]["actors"] = copy.deepcopy(data["actors"])
        aoe = copy.deepcopy(data["actors"])
        aoe[0]["hp"] -= 7
        aoe[1]["hp"] -= 12
        single = roster_hit(data["actors"], damage=3)
        plans = [response_plan(aoe, "aoe"), response_plan(single, "single")]
        data["states"][0]["rivalForecasts"] = [forecast(data["actors"], plans=plans)]
        detail = planner.decide(data)["trace"]["rivalResponses"]["root"][0]
        self.assertEqual((detail["risk"], detail["planId"]), (3, "single"))

    def test_only_ally_resource_losses_add_control_risk(self):
        data = snapshot()
        after = copy.deepcopy(data["actors"])
        after[0]["ap"] -= 2
        after[0]["wp"] -= 1
        after[1]["ap"] -= 6  # Rival resource expenditure does not count.
        data["policy"] = {"weights": {"control": 2}}
        data["states"][0]["rivalForecasts"] = [
            forecast(data["actors"], plans=[response_plan(after)])
        ]
        detail = planner.decide(data)["trace"]["rivalResponses"]["root"][0]
        self.assertEqual(detail["risk"], 6)

    def test_approximate_dependencies_are_reported_and_required(self):
        data = snapshot()
        data["states"][0]["rivalForecasts"] = [
            forecast(
                data["actors"],
                mode="approximate",
                unknown=["enemy_spell_policy"],
                plans=[],
            )
        ]
        result = planner.decide(data)
        detail = result["trace"]["rivalResponses"]["root"][0]
        self.assertEqual(detail["mode"], "approximate")
        self.assertEqual(detail["unknownDependencies"], ["enemy_spell_policy"])
        for unknown in ([], None):
            broken = snapshot()
            broken["states"][0]["rivalForecasts"] = [
                forecast(
                    broken["actors"], mode="approximate", unknown=unknown, plans=[]
                )
            ]
            with self.subTest(unknown=unknown), self.assertRaisesRegex(
                ValueError, "dependencies"
            ):
                planner.decide(broken)

    def test_scalar_threat_and_rival_forecasts_are_ambiguous(self):
        data = snapshot()
        data["states"][0].update(threat=2, rivalForecasts=[])
        with self.assertRaisesRegex(ValueError, "Ambiguous scalar"):
            planner.decide(data)

    def test_coverage_requires_root_and_each_state_and_omits_dead_rivals(self):
        data = snapshot()
        dead = copy.deepcopy(data["actors"])
        dead[1]["hp"] = 0
        data["states"][0]["transitions"] = [transition("kill", cast(1), "dead")]
        add_state(data, "dead", dead, rivalForecasts=[])
        # The root still forecasts the living enemy; the dead successor excludes it.
        data["states"][0]["rivalForecasts"] = [forecast(data["actors"], plans=[])]
        self.assertEqual(
            planner.decide(data)["trace"]["rivalResponses"]["selected"], []
        )

        missing_root = copy.deepcopy(data)
        missing_root["states"][0].pop("rivalForecasts")
        with self.assertRaisesRegex(ValueError, "Missing root rival forecasts"):
            planner.decide(missing_root)
        missing_successor = copy.deepcopy(data)
        missing_successor["states"][1].pop("rivalForecasts")
        with self.assertRaisesRegex(ValueError, "Inconsistent rival forecast coverage"):
            planner.decide(missing_successor)
        still_alive_omitted = snapshot()
        still_alive_omitted["states"][0]["rivalForecasts"] = [
            forecast(still_alive_omitted["actors"], plans=[])
        ]
        add_state(
            still_alive_omitted,
            "still-alive",
            still_alive_omitted["actors"],
            rivalForecasts=[],
        )
        still_alive_omitted["states"][0]["transitions"] = [
            transition("noop", cast(1), "still-alive")
        ]
        with self.assertRaisesRegex(ValueError, "Inconsistent rival forecast coverage"):
            planner.decide(still_alive_omitted)

    def test_duplicate_dead_or_foreign_rival_and_duplicate_plan_rejected(self):
        data = snapshot()
        one = forecast(data["actors"], plans=[])
        data["states"][0]["rivalForecasts"] = [one, copy.deepcopy(one)]
        with self.assertRaisesRegex(ValueError, "Invalid rival forecast actor"):
            planner.decide(data)

        for mutation, message in (
            (lambda f, actors: f.update(actorId=-2), "Invalid rival forecast actor"),
            (lambda f, actors: f.update(mode="future"), "projection mode"),
            (lambda f, actors: f.update(extra=True), "Invalid rival forecast fields"),
            (
                lambda f, actors: f.update(
                    plans=[response_plan(actors, "same"), response_plan(actors, "same")]
                ),
                "Duplicate rival response plan",
            ),
        ):
            broken = snapshot()
            f = forecast(broken["actors"], plans=[])
            mutation(f, broken["actors"])
            broken["states"][0]["rivalForecasts"] = [f]
            with self.subTest(message=message), self.assertRaisesRegex(
                ValueError, message
            ):
                planner.decide(broken)

        dead = snapshot()
        dead["actors"][1]["hp"] = 0
        dead["states"][0]["actors"] = copy.deepcopy(dead["actors"])
        dead["states"][0]["rivalForecasts"] = [forecast(dead["actors"], plans=[])]
        with self.assertRaisesRegex(ValueError, "Invalid rival forecast actor"):
            planner.decide(dead)

    def test_root_actors_preserve_identity_team_and_control(self):
        data = snapshot()
        future = copy.deepcopy(data["actors"])
        future[1]["ap"] = 0
        data["states"][0]["rivalForecasts"] = [
            forecast(data["actors"], root_actors=future, plans=[])
        ]
        self.assertEqual(
            planner.decide(data)["trace"]["rivalResponses"]["root"][0]["risk"], 0
        )
        for field, value in (("team", 1), ("controlled", False), ("id", 7)):
            broken = snapshot()
            altered = copy.deepcopy(broken["actors"])
            altered[1][field] = value
            broken["states"][0]["rivalForecasts"] = [
                forecast(broken["actors"], root_actors=altered, plans=[])
            ]
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "identities|ownership"
            ):
                planner.decide(broken)

    def test_dead_rival_cannot_act_again_in_supported_plan(self):
        data = snapshot()
        killed = copy.deepcopy(data["actors"])
        killed[1]["hp"] = 0
        plan = {
            "id": "after-death",
            "supported": True,
            "steps": [
                {"action": cast(-2, (0, 0, 0), spell_id=900), "actors": killed},
                {"action": {"type": "end_turn"}, "actors": killed},
            ],
        }
        data["states"][0]["rivalForecasts"] = [forecast(data["actors"], plans=[plan])]
        with self.assertRaisesRegex(ValueError, "Dead rival has outgoing action"):
            planner.decide(data)

    def test_legacy_v2_without_forecasts_and_protocol1_remain_accepted(self):
        data = snapshot()
        legacy = planner.decide(copy.deepcopy(data))
        self.assertEqual(legacy["decision"]["actions"], [{"type": "end_turn"}])

        v1 = {
            "protocol": 1,
            "requestId": "v1",
            "stateKey": "state-v1",
            "fight_id": 1,
            "actor_id": -2,
            "current_id": -2,
            "walkable": [[0, 0, 0], [1, 0, 0]],
            "edges": [],
            "actors": [
                actor(-2, 1, (0, 0, 0)),
                actor(1, 0, (1, 0, 0), controlled=True),
            ],
        }
        old = planner.decide(v1)
        self.assertEqual(old["protocol"], 1)
        self.assertIn("decision", old)

    def test_forecast_budgets_reject_excessive_steps(self):
        data = snapshot()
        extra = actor(2, 0, (2, 0, 2), controlled=True)
        data["actors"].append(extra)
        data["states"][0]["actors"].append(copy.deepcopy(extra))
        plans = [
            {
                "id": f"{rival}-{index}",
                "supported": False,
                "steps": [
                    {"action": {"type": "end_turn"}, "actors": []} for _ in range(16)
                ],
            }
            for rival in (1, 2)
            for index in range(16)
        ]
        forecasts = [
            forecast(
                data["actors"],
                rival=rival,
                plans=[p for p in plans if p["id"].startswith(f"{rival}-")],
            )
            for rival in (1, 2)
        ]
        data["states"][0]["rivalForecasts"] = forecasts
        add_state(data, "same", data["actors"], rivalForecasts=copy.deepcopy(forecasts))
        with self.assertRaisesRegex(ValueError, "Too many rival response steps"):
            planner.decide(data)

    def test_actor_record_budget_includes_unsupported_forecast_payloads(self):
        data = snapshot()
        # Unsupported evidence cannot authorize an action, but its serialized
        # roster still counts toward the request-size budget.
        records = [copy.deepcopy(data["actors"][0]) for _ in range(8193)]
        plan = {
            "id": "unsupported-large",
            "supported": False,
            "steps": [{"action": {"type": "end_turn"}, "actors": records}],
        }
        data["states"][0]["rivalForecasts"] = [forecast(data["actors"], plans=[plan])]
        with self.assertRaisesRegex(
            ValueError, "Too many rival forecast actor records"
        ):
            planner.decide(data)


if __name__ == "__main__":
    unittest.main()
