"""Search quota and partial incumbent hints remain source-bound advice."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_query_search import FakeNativeSession, fixture, run_search
from wakfu_ai.planning.query_search import search


class QueryBudgetSidecarTests(unittest.TestCase):
    def test_incumbent_is_published_only_after_a_certified_root_action(self):
        session = FakeNativeSession(
            spells=[dict(spellId=1, level=1)],
            cells=[(0, 0, 0), (3, 0, 0)],
            edges=[],
            effects={1: "damage"},
        )
        session.envelope["nativeBudgetMs"] = 20000
        observed = []
        original = session.request

        def request(query):
            observed.append(deepcopy(query))
            return original(query)

        session.request = request
        result = run_search(session)
        self.assertNotIn("incumbent", observed[0])
        first_preview = next(
            query for query in observed if query["operation"] == "preview"
        )
        self.assertNotIn("incumbent", first_preview)
        self.assertNotIn("searchAllowanceMs", first_preview)
        partials = [query["incumbent"] for query in observed if "incumbent" in query]
        self.assertTrue(partials)
        for partial in partials:
            self.assertEqual(partial["requestId"], session.envelope["requestId"])
            self.assertEqual(partial["sourceKey"], session.envelope["sourceKey"])
            self.assertEqual(partial["rootState"], session.envelope["rootState"])
            self.assertEqual(partial["plan"], [partial["action"]])
            self.assertEqual(partial["action"], first_preview["action"])
            self.assertTrue(partial["partial"])
            self.assertNotIn("score", partial)
            self.assertEqual(
                partial["unknownDependencies"], ["native_search_budget_partial"]
            )
        self.assertEqual(result["components"]["damage"], 5)

    def test_rival_query_allowance_stays_inside_500ms_phase_and_resets_raw_partial(
        self,
    ):
        session = FakeNativeSession(
            spells=[dict(spellId=1, level=1)],
            cells=[(0, 0, 0), (3, 0, 0)],
            edges=[],
            effects={1: "damage"},
        )
        session.envelope.update(nativeBudgetMs=20000, operations=["project_turn"])
        observed = []
        original = session.request

        def request(query):
            if query["operation"] == "project_turn":
                observed.append(deepcopy(query))
                return dict(
                    id=query["id"],
                    supported=False,
                    unknownDependencies=["fixture_projection_unavailable"],
                )
            return original(query)

        session.request = request
        result = run_search(session)
        self.assertTrue(observed)
        self.assertEqual(observed[0]["incumbent"]["action"]["type"], "cast")
        for query in observed:
            self.assertGreaterEqual(query["searchAllowanceMs"], 0)
            self.assertLessEqual(query["searchAllowanceMs"], 500)
            self.assertIn("incumbent", query)
        # After the first incomplete baseline, all certified independent
        # outcomes share unknown coverage. The useful cast remains eligible.
        self.assertEqual(observed[1]["incumbent"]["action"]["type"], "cast")
        self.assertEqual(result["action"]["spellId"], 1)
        self.assertIn("fixture_projection_unavailable", result["unknownDependencies"])

    def _risk_session(self):
        session = fixture(
            [dict(spellId=100, level=1), dict(spellId=200, level=1)],
            effects={100: "damage", 200: "heal"},
            edges=[],
        )
        session.root_state["actors"][0]["mp"] = 0
        session.root_state["actors"][1]["hp"] = 20
        session.envelope["policy"]["limits"].update(depth=1)
        session.envelope["policy"]["unknownRiskPenalty"] = 0
        session.envelope["operations"] = ["project_turn"]
        return session

    def test_timeout_after_known_heal_danger_keeps_assessed_end_turn(self):
        session = self._risk_session()
        assessed = []

        def forecast(state, *args, **kwargs):
            ally = next(actor for actor in state["actors"] if actor["id"] == 2)
            known = 100 if ally["hp"] > 20 else 0
            yield dict(id="risk-probe", operation="repertoire", state=state["key"])
            assessed.append(known)
            return dict(
                risk=known,
                knownLowerBound=known,
                complete=True,
                rivals=[],
                unknownDependencies=[],
            )

        with patch("wakfu_ai.planning.query_threat.forecast", forecast):
            driver = search(session.envelope, session.store, clock=lambda: 0)
            response = None
            risk_queries = []
            try:
                while True:
                    query = next(driver) if response is None else driver.send(response)
                    if query["id"] == "risk-probe":
                        risk_queries.append(deepcopy(query))
                        if len(assessed) == 2:
                            # Simulate HTTP cancellation before the next rival response.
                            self.assertEqual(assessed, [0, 100])
                            self.assertEqual(
                                risk_queries[0]["incumbent"]["action"]["spellId"], 200
                            )
                            self.assertIsNone(query["incumbent"])
                            break
                    response = session.request(query)
            finally:
                driver.close()
        self.assertEqual(len(risk_queries), 3)

    def test_partial_risk_coverage_matches_final_policy_without_double_imputation(self):
        session = self._risk_session()
        partials = []

        def forecast(state, *args, **kwargs):
            ally = next(actor for actor in state["actors"] if actor["id"] == 2)
            enemy = next(actor for actor in state["actors"] if actor["id"] == 9)
            heal = ally["hp"] > 20
            attacked = enemy["hp"] < 30
            if attacked:
                yield dict(
                    id="coverage-probe", operation="repertoire", state=state["key"]
                )
            known = 100 if heal else 0
            return dict(
                risk=known,
                knownLowerBound=known,
                complete=heal,
                rivals=[
                    dict(
                        actorId=9,
                        knownLowerBound=known,
                        complete=heal,
                        expanded=int(heal),
                    )
                ],
                unknownDependencies=[],
            )

        original = session.request

        def request(query):
            if query["id"] == "coverage-probe":
                partials.append(deepcopy(query["incumbent"]))
            return original(query)

        session.request = request
        with patch("wakfu_ai.planning.query_threat.forecast", forecast):
            result = run_search(session, clock=lambda: 0)
        # The unexpanded baseline inherits the observed danger. Its score is
        # -100, so healing (-92) beats it even during the next pending query.
        self.assertEqual(partials[0]["action"]["spellId"], 200)
        self.assertEqual(result["action"]["spellId"], 200)
        self.assertEqual(result["score"], -92)
        self.assertEqual(result["components"]["rival_risk_coverage_imputation"], 0)

    def test_new_coverage_danger_clears_previously_published_cast(self):
        session = self._risk_session()
        session.spells.append(dict(spellId=300, level=1))
        session.effects[300] = "damage"
        observed = []
        forecasts = []

        def forecast(state, *args, **kwargs):
            index = len(forecasts)
            forecasts.append(state)
            yield dict(id="reset-probe", operation="repertoire", state=state["key"])
            known = 100 if index >= 2 else 0
            complete = index != 1
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
                unknownDependencies=[],
            )

        original = session.request

        def request(query):
            if query["id"] == "reset-probe":
                observed.append(deepcopy(query["incumbent"]))
            return original(query)

        session.request = request
        with patch("wakfu_ai.planning.query_threat.forecast", forecast):
            result = run_search(session, clock=lambda: 0)
        self.assertGreaterEqual(len(observed), 4)
        self.assertEqual(observed[2]["action"]["spellId"], 200)
        # New evidence imputes 100 risk to the incomplete healing branch;
        # the fully assessed root becomes best and must clear that cast.
        self.assertTrue(all(partial is None for partial in observed[3:]))
        self.assertEqual(result["action"], {"type": "end_turn"})
        self.assertEqual(result["score"], 0)


if __name__ == "__main__":
    unittest.main()
