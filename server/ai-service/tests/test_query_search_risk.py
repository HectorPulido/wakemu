"""Integration regressions for rival-risk ranking in native query search."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_query_search import (
    ACTOR_ID,
    ENEMY_ID,
    ALLY_ID,
    FakeNativeSession,
    fixture,
    run_search,
)


def completed_forecast(*, known=0, complete=True, unknown=(), rivals=None):
    """Build a query_threat.forecast-compatible coroutine result."""

    def forecast(state, actor_id, store, weights, **kwargs):
        if False:
            yield None
        return {
            "risk": known if complete else None,
            "knownLowerBound": known,
            "complete": complete,
            "rivals": deepcopy(
                rivals
                if rivals is not None
                else [
                    {
                        "actorId": ENEMY_ID,
                        "risk": known if complete else None,
                        "knownLowerBound": known,
                        "complete": complete,
                        "unknownDependencies": list(unknown),
                    }
                ]
            ),
            "unknownDependencies": list(unknown),
        }

    return forecast


class ControlNativeSession(FakeNativeSession):
    """Native test double that exports an authoritative AP delta for spell 777."""

    def request(self, query):
        response = super().request(query)
        action = query.get("action", {})
        if (
            query["operation"] == "preview"
            and action.get("type") == "cast"
            and action.get("spellId") == 777
            and response.get("supported")
        ):
            enemy = next(
                row for row in response["result"]["actors"] if row["id"] == ENEMY_ID
            )
            enemy["ap"] -= 2
        return response


def invoke(session, forecast):
    session.envelope["operations"] = ["project_turn"]
    session.envelope["policy"].setdefault("weights", {}).update({"position": 0})
    with patch("wakfu_ai.planning.query_threat.forecast", forecast):
        return run_search(session)


class QuerySearchRiskTests(unittest.TestCase):
    def test_safe_position_can_beat_the_same_turn_baseline_by_certified_risk(self):
        session = fixture([], effects={})

        # Both candidates have equal tactical utility; only the world-certified
        # projected rival response differentiates their positions.
        def forecast(state, actor_id, store, weights, **kwargs):
            if False:
                yield None
            moved = next(row for row in state["actors"] if row["id"] == ACTOR_ID)[
                "position"
            ] != [0, 0, 0]
            risk = 0 if moved else 12
            return {
                "risk": risk,
                "knownLowerBound": risk,
                "complete": True,
                "rivals": [
                    {
                        "actorId": ENEMY_ID,
                        "risk": risk,
                        "knownLowerBound": risk,
                        "complete": True,
                        "unknownDependencies": [],
                    }
                ],
                "unknownDependencies": [],
            }

        result = invoke(session, forecast)

        self.assertEqual(result["action"], {"type": "move", "path": [[1, 0, 0]]})
        self.assertEqual(result["components"]["rival_risk_lower_bound"], 0)
        self.assertEqual(result["components"]["rival_risk_baseline"], 12)
        self.assertEqual(
            {
                row["forecast"]["rivals"][0]["actorId"]
                for row in result["rivalForecasts"]
            },
            {ENEMY_ID},
        )

    def test_healing_and_control_utility_remain_in_search_scores(self):
        healing = fixture(
            [{"spellId": 200, "level": 1}], effects={200: "heal"}, edges=[]
        )
        ally = next(
            row for row in healing.envelope["root"]["actors"] if row["id"] == ALLY_ID
        )
        ally["hp"] = 20
        healing.root_state["actors"] = deepcopy(healing.envelope["root"]["actors"])
        equal_risk = completed_forecast(known=0)

        healed = invoke(healing, equal_risk)
        self.assertEqual(healed["action"]["targetId"], ALLY_ID)
        self.assertEqual(healed["components"]["healing"], 8)
        self.assertIn("rival_risk_lower_bound", healed["components"])

        control = ControlNativeSession(
            spells=[{"spellId": 777, "level": 1}],
            cells=[(x, 0, 0) for x in range(4)] + [(0, 0, 1)],
            edges=[],
        )
        controlled = invoke(control, equal_risk)
        self.assertEqual(controlled["action"]["spellId"], 777)
        self.assertEqual(controlled["components"]["control"], 1)

    def test_incomplete_forecast_is_penalized_and_never_treated_as_zero_risk(self):
        session = fixture([], effects={})

        def forecast(state, actor_id, store, weights, **kwargs):
            if False:
                yield None
            moved = next(row for row in state["actors"] if row["id"] == ACTOR_ID)[
                "position"
            ] != [0, 0, 0]
            if moved:
                return {
                    "risk": None,
                    "knownLowerBound": 0,
                    "complete": False,
                    "rivals": [
                        {
                            "actorId": ENEMY_ID,
                            "risk": None,
                            "knownLowerBound": 0,
                            "complete": False,
                            "unknownDependencies": ["rival_candidate_budget_exhausted"],
                        }
                    ],
                    "unknownDependencies": ["rival_candidate_budget_exhausted"],
                }
            return {
                "risk": 0,
                "knownLowerBound": 0,
                "complete": True,
                "rivals": [
                    {
                        "actorId": ENEMY_ID,
                        "risk": 0,
                        "complete": True,
                        "unknownDependencies": [],
                    }
                ],
                "unknownDependencies": [],
            }

        result = invoke(session, forecast)

        self.assertEqual(result["action"], {"type": "end_turn"})
        uncertain = next(
            item
            for item in result["rivalForecasts"]
            if item["actions"] and item["actions"][0]["type"] == "move"
        )
        self.assertEqual(uncertain["forecast"]["risk"], None)
        self.assertEqual(uncertain["forecast"]["knownLowerBound"], 0)
        self.assertEqual(uncertain["score"], -25.1)
        self.assertIn("rival_candidate_budget_exhausted", result["unknownDependencies"])

    def test_shared_deadline_and_all_rival_results_survive_search_trace(self):
        session = fixture([], effects={})
        session.envelope["root"]["actors"].append(
            {
                "id": 10,
                "team": 0,
                "controlled": False,
                "position": [3, 0, 1],
                "hp": 30,
                "max_hp": 30,
                "armor": 0,
                "ap": 6,
                "mp": 3,
                "wp": 2,
            }
        )
        session.root_state["actors"] = deepcopy(session.envelope["root"]["actors"])
        calls = []
        all_rivals = [
            {
                "actorId": identity,
                "risk": None,
                "knownLowerBound": 0,
                "complete": False,
                "unknownDependencies": ["rival_search_deadline_reached"],
            }
            for identity in (ENEMY_ID, 10)
        ]

        def expired(state, actor_id, store, weights, **kwargs):
            if False:
                yield None
            calls.append(kwargs)
            return {
                "risk": None,
                "knownLowerBound": 0,
                "complete": False,
                "rivals": deepcopy(all_rivals),
                "unknownDependencies": ["rival_search_deadline_reached"],
            }

        result = invoke(session, expired)

        self.assertGreaterEqual(len(calls), 1)
        self.assertTrue(all(call["deadline"] == calls[0]["deadline"] for call in calls))
        self.assertIsInstance(calls[0]["deadline"], (int, float))
        self.assertTrue(
            all(row["forecast"]["risk"] is None for row in result["rivalForecasts"])
        )
        for row in result["rivalForecasts"]:
            self.assertEqual(
                {rival["actorId"] for rival in row["forecast"]["rivals"]},
                {ENEMY_ID, 10},
            )
        self.assertIn("rival_search_deadline_reached", result["unknownDependencies"])

    def test_invalid_rival_policy_fails_closed(self):
        cases = [
            ({"rivalLimits": {"unbounded": 1}}, "Invalid rival search policy"),
            ({"rivalLimits": {"nodes": 129}}, "Invalid rival search limit: nodes"),
            (
                {"unknownRiskPenalty": float("nan")},
                "Invalid unknown rival risk penalty",
            ),
        ]
        for update, message in cases:
            with self.subTest(update=update):
                session = fixture([], effects={})
                session.envelope["operations"] = ["project_turn"]
                session.envelope["policy"].update(update)
                with patch(
                    "wakfu_ai.planning.query_threat.forecast", completed_forecast()
                ):
                    with self.assertRaisesRegex(ValueError, message):
                        run_search(session)


if __name__ == "__main__":
    unittest.main()
