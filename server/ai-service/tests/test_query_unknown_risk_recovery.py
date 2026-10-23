"""Budget exhaustion must compare certified independent actions fairly."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_query_search import FakeNativeSession, run_search


class UnknownRiskRecoveryTests(unittest.TestCase):
    def run_case(
        self,
        *,
        baseline_risk=0,
        baseline_complete=False,
        timeout_first=True,
        damage=5,
        unknown_penalty=25,
        attributed=True
    ):
        session = FakeNativeSession(
            spells=[dict(spellId=1, level=1)],
            cells=[(0, 0, 0), (3, 0, 0)],
            edges=[],
            effects={1: "damage"},
        )
        session.root_state["actors"][0]["mp"] = 0
        session.envelope["policy"]["limits"].update(depth=1)
        session.envelope["operations"] = ["project_turn"]
        session.envelope["policy"]["unknownRiskPenalty"] = unknown_penalty
        forecasts, queries = [], []
        original = session.request

        def forecast(state, *args, **kwargs):
            forecasts.append(state["key"])
            root = state["key"] == session.envelope["rootState"]
            known = baseline_risk if root else 100
            complete = baseline_complete if root else False
            yield dict(id="recovery-risk", operation="repertoire", state=state["key"])
            exhausted = timeout_first or not root
            return dict(
                risk=known if complete else None,
                knownLowerBound=known,
                complete=complete,
                rivals=[
                    dict(
                        actorId=9, knownLowerBound=known, complete=complete, expanded=1
                    )
                ]
                if attributed
                else [],
                unknownDependencies=["native_search_allowance_exhausted"]
                if exhausted
                else [],
            )

        def request(query):
            queries.append(deepcopy(query))
            response = original(query)
            if (
                query["operation"] == "preview"
                and response["supported"]
                and query["action"].get("targetId") == 9
            ):
                next(
                    actor for actor in response["result"]["actors"] if actor["id"] == 9
                )["hp"] = (30 - damage)
            return response

        session.request = request
        with patch("wakfu_ai.planning.query_threat.forecast", forecast):
            decision = run_search(session, clock=lambda: 0)
        return decision, forecasts, queries

    def test_root_only_unknown_timeout_keeps_useful_certified_attack(self):
        decision, forecasts, _ = self.run_case()
        self.assertEqual(len(forecasts), 1)
        self.assertEqual(decision["action"]["type"], "cast")
        self.assertEqual(decision["components"]["damage"], 5)
        self.assertEqual(decision["components"]["rival_risk_uncertainty"], -25)
        self.assertIn("rival_response_not_evaluated", decision["unknownDependencies"])

    def test_observed_29_danger_is_imputed_to_unevaluated_attack(self):
        decision, forecasts, _ = self.run_case(baseline_risk=29)
        self.assertEqual(len(forecasts), 1)
        self.assertEqual(decision["action"]["type"], "cast")
        self.assertEqual(decision["components"]["rival_risk_coverage_imputation"], -29)
        self.assertEqual(decision["components"]["rival_risk_uncertainty"], -25)
        self.assertEqual(decision["score"], 5)
        self.assertEqual(decision["score"], sum(decision["components"].values()))

    def test_complete_safe_baseline_keeps_advantage_over_unknown_attack(self):
        decision, _, _ = self.run_case(baseline_complete=True)
        self.assertEqual(decision["action"], dict(type="end_turn"))
        self.assertEqual(decision["score"], 0)

    def test_known_unsafe_attack_is_not_replaced_with_a_zero_risk_estimate(self):
        decision, forecasts, _ = self.run_case(
            baseline_complete=True, timeout_first=False
        )
        self.assertGreaterEqual(len(forecasts), 2)
        self.assertEqual(decision["action"], dict(type="end_turn"))
        self.assertTrue(
            any(
                row["forecast"]["knownLowerBound"] == 100
                for row in decision["rivalForecasts"]
            )
        )

    def test_96_fixed_budget_cases_follow_the_same_unknown_risk_policy(self):
        for damage in (0, 1, 5, 29):
            for known in (0, 29):
                for complete in (False, True):
                    for uncertainty in (0, 25, 100):
                        with self.subTest(
                            damage=damage,
                            known=known,
                            complete=complete,
                            uncertainty=uncertainty,
                        ):
                            decision, forecasts, queries = self.run_case(
                                damage=damage,
                                baseline_risk=known,
                                baseline_complete=complete,
                                unknown_penalty=uncertainty,
                            )
                            expected = damage - (uncertainty if complete else 0)
                            self.assertEqual(len(forecasts), 1)
                            self.assertLessEqual(decision["expanded"], 96)
                            self.assertEqual(
                                decision["action"]["type"],
                                "cast" if expected > 0 else "end_turn",
                            )
                            self.assertEqual(decision["score"], max(0, expected))
                            self.assertAlmostEqual(
                                decision["score"], sum(decision["components"].values())
                            )
                            self.assertEqual(
                                sum(
                                    query["id"] == "recovery-risk" for query in queries
                                ),
                                1,
                            )

    def test_unattributed_aggregate_danger_is_not_lost_for_unknown_actions(self):
        decision, _, _ = self.run_case(baseline_risk=29, attributed=False)
        self.assertEqual(decision["action"]["type"], "cast")
        self.assertEqual(decision["components"]["rival_risk_coverage_imputation"], -29)
        self.assertEqual(decision["score"], 5)


if __name__ == "__main__":
    unittest.main()
