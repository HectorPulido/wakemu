"""One-action recovery must not borrow utility or risk from a combo tail."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_jondo_search_hybrid import PreparationSession, scenario_candidates
from test_query_search import run_search
from wakfu_ai.planning.query_search import search


class IndependentRecoveryTests(unittest.TestCase):
    def session(self):
        session = PreparationSession()
        # Model a preparation with no independent utility under an existing
        # supported policy; its certified progress still protects the beam.
        session.envelope["policy"]["featureWeights"] = {"owned_state_progress": 0}
        session.envelope["warmStart"] = dict(
            schema="verified-turn-continuation-v1",
            actions=[
                dict(type="cast", spellId=50, level=1, targetId=1, target=[0, 0, 0]),
                dict(type="cast", spellId=51, level=1, targetId=9, target=[9, 0, 0]),
            ],
        )
        return session

    def test_complete_combo_keeps_its_utility_but_rpc_fallback_uses_direct_attack(self):
        session = self.session()
        observed = []
        original = session.request

        def request(query):
            observed.append(deepcopy(query))
            return original(query)

        session.request = request
        with patch("wakfu_ai.planning.query_search.candidates", scenario_candidates):
            result = run_search(session, clock=lambda: 0)
        self.assertEqual([action["spellId"] for action in result["plan"]], [50, 51])
        self.assertEqual(result["components"]["damage"], 20)
        recovery = next(
            query["incumbent"]
            for query in observed
            if query["operation"] == "preview"
            and query["state"] == "root-state"
            and query["action"]["spellId"] == 10
        )
        self.assertEqual(recovery["action"]["spellId"], 9)
        self.assertEqual(recovery["plan"], [recovery["action"]])
        self.assertEqual(recovery["rootState"], "root-state")
        self.assertNotIn("score", recovery)
        after_equal_attack = next(
            query["incumbent"]
            for query in observed
            if query["operation"] == "preview"
            and query["state"] == "root-state"
            and query["action"]["spellId"] == 11
        )
        self.assertEqual(after_equal_attack["action"]["spellId"], 9)
        self.assertIsNone(result["searchBudgetEvidence"]["recoverySelection"])

    def test_allowance_exhaustion_returns_certified_single_action_not_setup(self):
        session = self.session()
        original = session.request
        timeouts = []

        def request(query):
            if (
                query["operation"] == "preview"
                and query["state"] == "root-state"
                and query["action"]["spellId"] == 10
            ):
                timeouts.append(deepcopy(query))
                return dict(
                    id=query["id"],
                    supported=False,
                    unknownDependencies=["native_search_allowance_exhausted"],
                )
            return original(query)

        session.request = request
        with patch("wakfu_ai.planning.query_search.candidates", scenario_candidates):
            result = run_search(session, clock=lambda: 0)
        self.assertEqual(len(timeouts), 1)
        self.assertEqual(result["action"]["spellId"], 9)
        self.assertEqual(result["plan"], [result["action"]])
        self.assertEqual(result["components"]["damage"], 2)
        self.assertEqual(
            result["searchBudgetEvidence"]["recoverySelection"],
            "certified_single_action",
        )
        self.assertEqual(result["score"], sum(result["components"].values()))

    def test_zero_utility_preparation_clears_rpc_fallback_until_direct_attack(self):
        session = self.session()
        observed = []
        original = session.request

        def request(query):
            if query["operation"] == "preview" and query["action"]["spellId"] == 51:
                observed.append(deepcopy(query))
            return original(query)

        session.request = request
        with patch("wakfu_ai.planning.query_search.candidates", scenario_candidates):
            run_search(session, clock=lambda: 0)
        self.assertIsNone(observed[0]["incumbent"])

    def test_cancelling_rpc_after_completed_combo_keeps_direct_attack_snapshot(self):
        session = self.session()
        response = None
        with patch("wakfu_ai.planning.query_search.candidates", scenario_candidates):
            driver = search(session.envelope, session.store, clock=lambda: 0)
            try:
                while True:
                    query = next(driver) if response is None else driver.send(response)
                    if (
                        query["operation"] == "preview"
                        and query["state"] == "root-state"
                        and query["action"]["spellId"] == 10
                    ):
                        self.assertEqual(query["incumbent"]["action"]["spellId"], 9)
                        self.assertEqual(
                            query["incumbent"]["sourceKey"],
                            session.envelope["sourceKey"],
                        )
                        self.assertTrue(
                            any(
                                action["spellId"] == 51
                                for action in session.preview_actions
                            )
                        )
                        break
                    response = session.request(query)
            finally:
                driver.close()

    def test_risk_recovery_never_uses_combo_endpoint_as_prefix_forecast(self):
        for single_risk, complete in ((0, True), (100, True), (0, False)):
            with self.subTest(single_risk=single_risk, complete=complete):
                session = self.session()
                session.envelope["operations"] = ["project_turn"]
                observed = []
                original = session.request

                def forecast(state, *args, **kwargs):
                    losses = [
                        30 - actor["hp"]
                        for actor in state["actors"]
                        if actor["team"] == 0
                    ]
                    single = max(losses) == 2
                    known = single_risk if single else 0
                    finished = complete if single else True
                    yield dict(
                        id="independent-risk",
                        operation="repertoire",
                        state=state["key"],
                    )
                    return dict(
                        risk=known,
                        knownLowerBound=known,
                        complete=finished,
                        rivals=[
                            dict(
                                actorId=9,
                                knownLowerBound=known,
                                complete=finished,
                                expanded=int(finished),
                            )
                        ],
                        unknownDependencies=[]
                        if finished
                        else ["fixture_unknown_risk"],
                    )

                def request(query):
                    if query["id"] == "independent-risk":
                        observed.append(deepcopy(query))
                    return original(query)

                session.request = request
                with patch(
                    "wakfu_ai.planning.query_search.candidates", scenario_candidates
                ), patch("wakfu_ai.planning.query_threat.forecast", forecast):
                    result = run_search(session, clock=lambda: 0)
                self.assertGreaterEqual(len(observed), 3)
                # Root and complete combo have been assessed before this
                # query, but no useful standalone action has its own forecast.
                self.assertIsNone(observed[2]["incumbent"])
                # The first query may carry an all-unknown certified seed.
                # Once the complete baseline returns, its known coverage wins
                # over unassessed singleton forecasts until they are evaluated.
                partials = [
                    query["incumbent"]
                    for query in observed[1:]
                    if query["incumbent"] is not None
                ]
                if single_risk == 0 and complete:
                    self.assertTrue(partials)
                    self.assertTrue(
                        all(
                            item["action"]["spellId"] in (9, 10, 11)
                            for item in partials
                        )
                    )
                else:
                    self.assertFalse(partials)
                self.assertEqual(
                    [action["spellId"] for action in result["plan"]], [50, 51]
                )

    def test_allowance_exhaustion_during_combo_risk_returns_assessed_root(self):
        session = self.session()
        session.envelope["operations"] = ["project_turn"]
        seen = []

        def forecast(state, *args, **kwargs):
            losses = [
                30 - actor["hp"] for actor in state["actors"] if actor["team"] == 0
            ]
            seen.append(max(losses))
            if max(losses) == 20:
                yield dict(id="risk-expiry", operation="repertoire", state=state["key"])
                return dict(
                    risk=0,
                    knownLowerBound=0,
                    complete=False,
                    rivals=[],
                    unknownDependencies=["native_search_allowance_exhausted"],
                )
            return dict(
                risk=0,
                knownLowerBound=0,
                complete=True,
                rivals=[],
                unknownDependencies=[],
            )

        with patch(
            "wakfu_ai.planning.query_search.candidates", scenario_candidates
        ), patch("wakfu_ai.planning.query_threat.forecast", forecast):
            result = run_search(session, clock=lambda: 0)
        self.assertEqual(seen, [0, 20])
        self.assertEqual(result["action"], {"type": "end_turn"})
        self.assertEqual(result["plan"], [])
        self.assertEqual(
            result["searchBudgetEvidence"]["recoverySelection"], "end_turn"
        )
        self.assertIn(
            "native_search_allowance_exhausted",
            result["searchBudgetEvidence"]["stopReasons"],
        )

    def test_risk_recovery_retains_coverage_imputation_in_score_components(self):
        session = self.session()
        session.envelope["operations"] = ["project_turn"]
        assessed = []

        def forecast(state, *args, **kwargs):
            index = len(assessed)
            assessed.append(state["key"])
            known = 100 if index == 1 else 0
            complete = index == 1
            yield dict(id="risk-imputation", operation="repertoire", state=state["key"])
            return dict(
                risk=known,
                knownLowerBound=known,
                complete=complete,
                rivals=[
                    dict(
                        actorId=9,
                        knownLowerBound=known,
                        complete=complete,
                        expanded=int(complete),
                    )
                ],
                unknownDependencies=["native_search_allowance_exhausted"]
                if index == 3
                else [],
            )

        with patch(
            "wakfu_ai.planning.query_search.candidates", scenario_candidates
        ), patch("wakfu_ai.planning.query_threat.forecast", forecast):
            result = run_search(session, clock=lambda: 0)
        self.assertEqual(len(assessed), 4)
        self.assertEqual(len(result["plan"]), 1)
        self.assertIn(result["action"]["spellId"], (9, 10, 11))
        self.assertEqual(result["components"]["rival_risk_coverage_imputation"], -100)
        self.assertAlmostEqual(result["score"], -98.1)
        self.assertAlmostEqual(result["score"], sum(result["components"].values()))


if __name__ == "__main__":
    unittest.main()
