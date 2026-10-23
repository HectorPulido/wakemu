"""Recovery advice retains certified matching tails without adopting outcomes."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_query_search import FakeNativeSession, run_search
from test_turn_continuation import runtime, bind
import test_query_independent_recovery as independent_fixtures
from test_jondo_search_hybrid import scenario_candidates
from wakfu_ai.planning import turn_continuation as custody


MOVE = dict(type="move", path=[[1, 0, 0]])
ATTACK = dict(type="cast", spellId=1, level=1, targetId=9, target=[3, 0, 0])


def bad(identity):
    return dict(ATTACK, spellId=identity)


class AdviceSession(FakeNativeSession):
    def __init__(self, *, expires=True, moved=False):
        cells = [(x, 0, 0) for x in range(4)]
        super().__init__(
            spells=[dict(spellId=1, level=1)],
            cells=cells,
            edges=list(zip(cells, cells[1:])),
            effects={1: "damage"},
            cast_requires_move=True,
        )
        self.expires = expires
        self.queries = []
        self.root_state["actors"][0].update(
            mp=0 if moved else 1, position=[1, 0, 0] if moved else [0, 0, 0]
        )
        self.envelope["policy"]["limits"].update(
            depth=2, beam=2, nodes=16, probeQuantum=1
        )

    def request(self, query):
        self.queries.append(deepcopy(query))
        if query["operation"] == "preview" and query["action"].get("spellId", 0) >= 99:
            return dict(
                id=query["id"],
                supported=False,
                unknownDependencies=[
                    "native_search_allowance_exhausted"
                    if self.expires
                    else "fixture_illegal"
                ],
            )
        return super().request(query)


def initial_candidates(graph, state, repertoire, actor_id, *args, **kwargs):
    if state["actors"][0]["position"] == [0, 0, 0]:
        yield deepcopy(MOVE)
        yield bad(99)
    else:
        yield deepcopy(ATTACK)


def crowded_candidates(graph, state, repertoire, actor_id, *args, **kwargs):
    for identity in (99, 100, 101, 102):
        yield bad(identity)
    yield deepcopy(ATTACK)


class RecoveryContinuationAdviceTests(unittest.TestCase):
    def recovered(self):
        session = AdviceSession()
        with patch("wakfu_ai.planning.query_search.candidates", initial_candidates):
            decision = run_search(session, clock=lambda: 0)
        return session, decision

    def test_matching_tail_does_not_change_independent_action_score_or_plan(self):
        session, decision = self.recovered()
        self.assertEqual(decision["action"], MOVE)
        self.assertEqual(decision["plan"], [MOVE])
        self.assertEqual(decision["components"]["damage"], 0)
        self.assertAlmostEqual(decision["score"], sum(decision["components"].values()))
        proposal = decision["recoveryContinuation"]
        self.assertEqual(proposal["rootAction"], MOVE)
        self.assertEqual(proposal["actions"], [ATTACK])
        self.assertEqual(proposal["sourceKey"], session.envelope["sourceKey"])
        self.assertEqual(proposal["rootState"], session.envelope["rootState"])
        self.assertEqual(proposal["requestId"], session.envelope["requestId"])
        self.assertNotIn("score", proposal)
        self.assertTrue(
            any(
                query["operation"] == "preview"
                and query["action"] == ATTACK
                and query["state"] != "root-state"
                for query in session.queries
            )
        )

    def test_confirmed_advice_is_freshly_previewed_and_improves_fixed_query_budget(
        self,
    ):
        _, decision = self.recovered()
        value = runtime()
        source = bind(
            value,
            source=decision["sourceKey"],
            root=decision["rootState"],
            request=decision["requestId"],
        )
        holder = custody.TurnContinuation(publication_required=True)
        value.fight.sequence += 1  # Actual publication boundary is explicit.
        holder.stage(decision, source, value)
        self.assertIsNone(holder.proposal(value, bind(value)))
        holder.stage(decision, source, value)
        holder.confirm(value, action=MOVE)
        fresh = bind(value, source="fresh", root="fresh-root", request="fresh-request")
        proposal = holder.proposal(value, fresh)
        self.assertEqual(proposal["actions"], [ATTACK])
        rows = []
        for advice in (None, proposal):
            session = AdviceSession(expires=False, moved=True)
            session.envelope["policy"]["limits"]["nodes"] = 4
            if advice is not None:
                session.envelope["warmStart"] = advice
            with patch("wakfu_ai.planning.query_search.candidates", crowded_candidates):
                result = run_search(session, clock=lambda: 0)
            rows.append((session, result))
        self.assertEqual(rows[0][1]["components"].get("damage", 0), 0)
        self.assertEqual(rows[1][1]["components"]["damage"], 5)
        self.assertEqual(len(rows[0][0].queries), len(rows[1][0].queries))
        self.assertEqual(len(rows[1][0].queries), 5)
        self.assertEqual(rows[1][0].queries[0]["state"], "root-state")
        self.assertEqual(rows[1][0].queries[0]["action"], ATTACK)
        self.assertEqual(rows[1][1]["searchBudgetEvidence"]["warmStartAccepted"], 1)

    def test_wrong_root_action_or_provenance_never_enters_custody(self):
        _, decision = self.recovered()
        for mutation in (
            dict(rootAction=bad(99)),
            dict(sourceKey="foreign"),
            dict(rootState="foreign"),
            dict(requestId="foreign"),
            dict(schema="unknown"),
            dict(actions=[dict(type="end_turn")]),
        ):
            with self.subTest(mutation=mutation):
                changed = deepcopy(decision)
                changed["recoveryContinuation"].update(mutation)
                value = runtime()
                holder = custody.TurnContinuation()
                source = bind(
                    value,
                    source=decision["sourceKey"],
                    root=decision["rootState"],
                    request=decision["requestId"],
                )
                holder.stage(changed, source, value)
                holder.confirm(value, action=MOVE)
                self.assertIsNone(holder.proposal(value, source))

    def test_fresh_rejection_of_advised_attack_does_not_execute_it(self):
        _, decision = self.recovered()
        session = AdviceSession(expires=False, moved=True)
        session.envelope["warmStart"] = dict(
            schema=custody.SCHEMA, actions=decision["recoveryContinuation"]["actions"]
        )
        session.reject_all = True
        with patch("wakfu_ai.planning.query_search.candidates", crowded_candidates):
            result = run_search(session, clock=lambda: 0)
        self.assertEqual(result["action"], dict(type="end_turn"))
        self.assertEqual(result["searchBudgetEvidence"]["warmStartAccepted"], 0)

    def test_combo_with_different_first_action_cannot_supply_recovery_advice(self):
        session = independent_fixtures.IndependentRecoveryTests().session()
        original = session.request

        def request(query):
            if (
                query["operation"] == "preview"
                and query["state"] == "root-state"
                and query["action"].get("spellId") == 10
            ):
                return dict(
                    id=query["id"],
                    supported=False,
                    unknownDependencies=["native_search_allowance_exhausted"],
                )
            return original(query)

        session.request = request
        with patch("wakfu_ai.planning.query_search.candidates", scenario_candidates):
            decision = run_search(session, clock=lambda: 0)
        self.assertEqual(decision["action"]["spellId"], 9)
        self.assertNotIn("recoveryContinuation", decision)

    def test_bounded_advice_is_copied_and_portal_action_is_normalized(self):
        portal = dict(type="portal_travel", destination=[8, 9, -1])
        actions = [portal, ATTACK, MOVE, bad(99)]
        proposal = custody.recovery_proposal(
            actions, root_action=MOVE, source="source", root="root", request="request"
        )
        self.assertEqual(len(proposal["actions"]), 3)
        actions[0]["destination"][0] = 99
        self.assertEqual(proposal["actions"][0]["destination"], [8, 9, -1])
        from wakfu_ai.planning.query_search import _warm_start_actions

        self.assertEqual(
            _warm_start_actions(
                dict(schema=custody.SCHEMA, actions=proposal["actions"])
            ),
            proposal["actions"],
        )

    def test_certified_tail_outside_risk_shortlist_remains_fresh_advice_only(self):
        session = AdviceSession(expires=False)
        # This tail has worse own utility than its independent movement.
        # It is consequently absent from the two-option risk shortlist.
        session.effects[1] = "friendly_fire"
        session.envelope["operations"] = ["project_turn"]
        session.envelope["policy"].update(
            rivalLimits=dict(alternatives=2), unknownRiskPenalty=0
        )
        assessed = []

        def forecast(state, *args, **kwargs):
            assessed.append(deepcopy(state))
            moved = state["actors"][0]["position"] == [1, 0, 0]
            if moved:
                yield dict(
                    id="tail-outside-shortlist",
                    operation="repertoire",
                    state=state["key"],
                )
            return dict(
                risk=0,
                knownLowerBound=0,
                complete=not moved,
                rivals=[],
                unknownDependencies=["native_search_allowance_exhausted"]
                if moved
                else [],
            )

        with patch(
            "wakfu_ai.planning.query_search.candidates", initial_candidates
        ), patch("wakfu_ai.planning.query_threat.forecast", forecast):
            decision = run_search(session, clock=lambda: 0)
        self.assertEqual(len(assessed), 2)
        self.assertTrue(all(state["actors"][0]["hp"] == 30 for state in assessed))
        self.assertEqual(decision["action"], MOVE)
        self.assertEqual(decision["plan"], [MOVE])
        self.assertEqual(decision["components"]["damage"], 0)
        self.assertAlmostEqual(decision["score"], sum(decision["components"].values()))
        proposal = decision["recoveryContinuation"]
        self.assertEqual(proposal["rootAction"], MOVE)
        self.assertEqual(proposal["actions"], [ATTACK])
        self.assertNotIn("riskForecast", proposal)
        # A fresh native search still sees the actual self-damage and rejects
        # this advice as the final action; retained advice is no authorization.
        fresh = AdviceSession(expires=False, moved=True)
        fresh.effects[1] = "friendly_fire"
        fresh.envelope["warmStart"] = dict(
            schema=custody.SCHEMA, actions=proposal["actions"]
        )
        with patch("wakfu_ai.planning.query_search.candidates", crowded_candidates):
            result = run_search(fresh, clock=lambda: 0)
        self.assertEqual(result["searchBudgetEvidence"]["warmStartAccepted"], 1)
        self.assertEqual(result["action"], dict(type="end_turn"))


if __name__ == "__main__":
    unittest.main()
