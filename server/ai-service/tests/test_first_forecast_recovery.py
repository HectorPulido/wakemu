"""Staged incoming risk queries retain explicitly unknown independent recovery."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_query_search as fixtures
from test_jondo_search_hybrid import PreparationSession, scenario_candidates
from wakfu_ai.bridge.world_bridge import NativeSession

_SOURCE = (
    Path(__file__).resolve().parents[1] / "wakfu_ai" / "planning" / "query_search.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "wakfu_ai.planning._staged_seeded_risk", _SOURCE
)
candidate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(candidate)
ATTACK = dict(type="cast", spellId=1, level=1, target=[3, 0, 0], targetId=9)


def risk(known=0, complete=False, exhausted=False):
    return dict(
        risk=known if complete else None,
        knownLowerBound=known,
        complete=complete,
        rivals=[
            dict(
                actorId=9,
                knownLowerBound=known,
                complete=complete,
                expanded=int(complete or known > 0),
            )
        ],
        unknownDependencies=["native_search_allowance_exhausted"] if exhausted else [],
    )


class FirstForecastRecoveryTests(unittest.TestCase):
    def session(self, *, effect="damage"):
        value = fixtures.FakeNativeSession(
            spells=[dict(spellId=1, level=1)],
            cells=[(0, 0, 0), (3, 0, 0)],
            edges=[],
            effects={1: effect},
        )
        value.root_state["actors"][0]["mp"] = 0
        value.envelope["policy"]["limits"].update(depth=1)
        value.envelope["operations"] = ["project_turn"]
        return value

    def first_risk_query(self, session, forecast):
        driver = candidate.search(session.envelope, session.store, clock=lambda: 0)
        answer = None
        with patch("wakfu_ai.planning.query_threat.forecast", forecast):
            try:
                while True:
                    query = next(driver) if answer is None else driver.send(answer)
                    if query["id"] == "first-risk":
                        return deepcopy(query)
                    answer = session.request(query)
            finally:
                driver.close()

    def test_first_incoming_forecast_query_survives_rpc_timeout_with_recertified_attack(
        self,
    ):
        session = self.session()

        def forecast(*args, **kwargs):
            yield dict(
                id="first-risk", operation="project_turn", state="root-state", actorId=9
            )
            return risk(exhausted=True)

        query = self.first_risk_query(session, forecast)
        incumbent = query["incumbent"]
        self.assertEqual(incumbent["action"], ATTACK)
        self.assertEqual(incumbent["plan"], [ATTACK])
        self.assertNotIn("score", incumbent)
        previews = []
        owner = NativeSession.__new__(NativeSession)
        owner.request_id, owner.source, owner.root = (
            session.envelope[key] for key in ("requestId", "sourceKey", "rootState")
        )
        owner._certified_root_actions = {owner._action_key(ATTACK)}
        owner.guard = lambda: None
        owner.oracle = SimpleNamespace(
            runtime=object(),
            preview=lambda value, action: previews.append(deepcopy(action)),
        )
        certified = owner._certified_incumbent(incumbent)
        self.assertIsNotNone(certified)
        recovered = owner._partial_decision(certified)
        self.assertEqual(recovered["action"], ATTACK)
        self.assertEqual(recovered["plan"], [ATTACK])
        self.assertEqual(previews, [ATTACK])

    def test_no_positive_standalone_outcome_seeds_no_action(self):
        session = self.session(effect="none")

        def forecast(*args, **kwargs):
            yield dict(
                id="first-risk", operation="project_turn", state="root-state", actorId=9
            )
            return risk()

        self.assertIsNone(self.first_risk_query(session, forecast)["incumbent"])

    def test_first_forecast_does_not_borrow_complete_combo_utility_for_setup(self):
        session = PreparationSession()
        session.envelope["operations"] = ["project_turn"]
        session.envelope["warmStart"] = dict(
            schema="verified-turn-continuation-v1",
            actions=[
                dict(type="cast", spellId=50, level=1, targetId=1, target=[0, 0, 0]),
                dict(type="cast", spellId=51, level=1, targetId=9, target=[9, 0, 0]),
            ],
        )

        def forecast(*args, **kwargs):
            yield dict(
                id="first-risk", operation="project_turn", state="root-state", actorId=9
            )
            return risk()

        with patch.object(candidate, "candidates", scenario_candidates):
            query = self.first_risk_query(session, forecast)
        self.assertIn(query["incumbent"]["action"]["spellId"], (9, 10, 11))
        self.assertNotEqual(query["incumbent"]["action"]["spellId"], 50)

    def test_complete_first_baseline_replaces_provisional_unknown_scores(self):
        session = self.session()
        observed = []
        original = session.request

        def forecast(state, *args, **kwargs):
            root = state["key"] == "root-state"
            yield dict(
                id="first-risk" if root else "later-risk",
                operation="repertoire",
                state=state["key"],
            )
            return risk(complete=root, exhausted=not root)

        def request(query):
            if query["id"] in ("first-risk", "later-risk"):
                observed.append(deepcopy(query))
            return original(query)

        session.request = request
        with patch.object(fixtures, "search", candidate.search), patch(
            "wakfu_ai.planning.query_threat.forecast", forecast
        ):
            result = fixtures.run_search(session, clock=lambda: 0)
        self.assertEqual(observed[0]["incumbent"]["action"], ATTACK)
        self.assertIsNone(observed[1]["incumbent"])
        self.assertEqual(result["action"], dict(type="end_turn"))
        self.assertEqual(result["score"], 0)

    def test_first_known_29_baseline_does_not_leave_provisional_scores_cached(self):
        session = self.session()

        def forecast(state, *args, **kwargs):
            root = state["key"] == "root-state"
            yield dict(
                id="first-risk" if root else "later-risk",
                operation="repertoire",
                state=state["key"],
            )
            return risk(known=29 if root else 0, exhausted=not root)

        with patch.object(fixtures, "search", candidate.search), patch(
            "wakfu_ai.planning.query_threat.forecast", forecast
        ):
            result = fixtures.run_search(session, clock=lambda: 0)
        self.assertEqual(result["action"], ATTACK)
        self.assertEqual(result["score"], 5)
        self.assertEqual(result["components"]["rival_risk_coverage_imputation"], -29)
        self.assertEqual(result["score"], sum(result["components"].values()))


if __name__ == "__main__":
    unittest.main()
