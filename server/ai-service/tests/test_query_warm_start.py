"""Published continuations remain bounded proposals for fresh native previews."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_query_search import FakeNativeSession, run_search
from test_jondo_search_hybrid import PreparationSession, scenario_candidates


def cast(spell, target=9):
    return dict(
        type="cast",
        spellId=spell,
        level=1,
        targetId=target,
        target=[3, 0, 0] if target == 9 else [0, 0, 0],
    )


def hint(session, actions):
    session.envelope["warmStart"] = dict(
        schema="verified-turn-continuation-v1", actions=deepcopy(actions)
    )


class WarmStartTests(unittest.TestCase):
    def test_normal_stream_reuses_the_fresh_warm_preview(self):
        session = FakeNativeSession(
            spells=[dict(spellId=1, level=1)],
            cells=[(0, 0, 0), (3, 0, 0)],
            edges=[],
            effects={1: "damage"},
        )
        hint(session, [cast(1)])
        attempts = []
        original = session.request

        def request(query):
            if query["operation"] == "preview":
                attempts.append((query["state"], deepcopy(query["action"])))
            return original(query)

        session.request = request
        result = run_search(session)
        self.assertEqual(attempts.count(("root-state", cast(1))), 1)
        self.assertEqual(result["action"], cast(1))
        self.assertEqual(result["components"]["damage"], 5)

    def test_normal_stream_does_not_repeat_a_rejected_warm_preview(self):
        session = FakeNativeSession(
            spells=[dict(spellId=1, level=1)],
            cells=[(0, 0, 0), (3, 0, 0)],
            edges=[],
            reject_all=True,
        )
        hint(session, [cast(1)])
        attempts = []
        original = session.request

        def request(query):
            if query["operation"] == "preview":
                attempts.append((query["state"], deepcopy(query["action"])))
            return original(query)

        session.request = request
        result = run_search(session)
        self.assertEqual(attempts.count(("root-state", cast(1))), 1)
        self.assertEqual(result["action"]["type"], "end_turn")

    def test_reused_attack_keeps_fresh_normal_followups_eligible(self):
        session = FakeNativeSession(
            spells=[dict(spellId=i, level=1) for i in (1, 2)],
            cells=[(0, 0, 0), (3, 0, 0)],
            edges=[],
            effects={1: "damage", 2: "heal"},
        )
        session.root_state["actors"][1]["hp"] = 10
        session.envelope["policy"]["limits"].update(depth=2)
        hint(session, [cast(1)])
        healing = dict(type="cast", spellId=2, level=1, targetId=2, target=[0, 0, 1])

        def candidates(graph, state, *args, **kwargs):
            yield cast(1) if state["key"] == "root-state" else deepcopy(healing)

        with patch("wakfu_ai.planning.query_search.candidates", candidates):
            result = run_search(session)
        self.assertEqual(result["plan"], [cast(1), healing])
        self.assertEqual(result["searchBudgetEvidence"]["warmStartReused"], 1)

    def test_warm_preview_reuse_does_not_cross_decisions(self):
        for rejected in (False, True):
            session = FakeNativeSession(
                spells=[dict(spellId=1, level=1)],
                cells=[(0, 0, 0), (3, 0, 0)],
                edges=[],
                effects={1: "damage"},
                reject_all=rejected,
            )
            hint(session, [cast(1)])
            result = run_search(session)
            self.assertEqual(session.preview_actions.count(cast(1)), 1)
            self.assertEqual(
                result["searchBudgetEvidence"]["warmStartAccepted"],
                0 if rejected else 1,
            )

    def test_same_query_budget_finds_useful_previous_cast_before_cold_stream(self):
        results = []
        for warm in (False, True):
            session = FakeNativeSession(
                spells=[
                    dict(spellId=identity, level=1) for identity in (*range(1, 13), 99)
                ],
                cells=[(0, 0, 0), (3, 0, 0)],
                edges=[],
                effects={99: "damage"},
            )
            session.envelope["policy"]["limits"].update(depth=1, beam=2, nodes=4)
            if warm:
                hint(session, [cast(99)])
            queries = Counter()
            original = session.request

            def request(query):
                queries[query["operation"]] += 1
                return original(query)

            session.request = request
            result = run_search(session)
            results.append((result, queries))
        self.assertEqual(results[0][0]["action"]["type"], "end_turn")
        self.assertEqual(results[1][0]["action"]["spellId"], 99)
        self.assertEqual(results[1][0]["components"]["damage"], 5)
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(results[1][1], dict(preview=4, repertoire=1))

    def test_setup_followup_is_repreviewed_on_each_fresh_source(self):
        session = PreparationSession()
        hint(session, [cast(50, 1), cast(51)])
        sources = []
        original = session.request

        def request(query):
            if query["operation"] == "preview":
                sources.append(query["state"])
            return original(query)

        session.request = request
        with patch("wakfu_ai.planning.query_search.candidates", scenario_candidates):
            result = run_search(session)
        self.assertEqual([step["spellId"] for step in result["plan"]], [50, 51])
        self.assertEqual(sources[:2], ["root-state", "state-1"])
        self.assertEqual(result["searchBudgetEvidence"]["warmStartAccepted"], 2)

    def test_better_fresh_alternative_beats_warm_incumbent(self):
        session = FakeNativeSession(
            spells=[dict(spellId=identity, level=1) for identity in (1, 2)],
            cells=[(0, 0, 0), (3, 0, 0)],
            edges=[],
            effects={1: "safe_damage", 2: "damage"},
        )
        hint(session, [cast(1)])
        result = run_search(session)
        self.assertEqual(result["action"]["spellId"], 2)
        self.assertEqual(result["components"]["damage"], 5)

    def test_rejected_hint_stops_tail_and_preserves_alternative_search(self):
        session = FakeNativeSession(
            spells=[dict(spellId=1, level=1)],
            cells=[(0, 0, 0), (3, 0, 0)],
            edges=[],
            effects={1: "damage"},
        )
        hint(session, [cast(99), cast(98)])
        original = session.request

        def request(query):
            if query["operation"] == "preview" and query["action"].get("spellId") == 99:
                return dict(
                    id=query["id"],
                    supported=False,
                    unknownDependencies=["fresh_native_rejection"],
                )
            return original(query)

        session.request = request
        result = run_search(session)
        self.assertEqual(result["action"]["spellId"], 1)
        self.assertEqual(result["searchBudgetEvidence"]["warmStartAccepted"], 0)
        self.assertIn("fresh_native_rejection", result["unknownDependencies"])
        self.assertFalse(
            any(action.get("spellId") == 98 for action in session.preview_actions)
        )

    def test_malformed_hint_is_ignored_without_executing_partial_prefix(self):
        for actions in (
            [cast(1)] * 4,
            [cast(1), {"type": "end_turn"}],
            [dict(type="move", path=[[True, 0, 0]])],
        ):
            with self.subTest(actions=actions):
                session = FakeNativeSession(
                    spells=[dict(spellId=1, level=1)],
                    cells=[(0, 0, 0), (3, 0, 0)],
                    edges=[],
                    effects={1: "damage"},
                )
                hint(session, actions)
                result = run_search(session)
                self.assertEqual(result["action"]["spellId"], 1)
                self.assertEqual(result["searchBudgetEvidence"]["warmStartPreviews"], 0)

    def test_hostile_damage_truncates_old_approach_tail(self):
        session = FakeNativeSession(
            spells=[], cells=[(0, 0, 0), (3, 0, 0)], edges=[], effects={99: "damage"}
        )
        hint(session, [cast(99), dict(type="move", path=[[1, 0, 0]])])
        result = run_search(session)
        self.assertEqual(result["searchBudgetEvidence"]["warmStartPreviews"], 1)
        self.assertEqual(result["plan"], [cast(99)])
        self.assertFalse(
            any(action["type"] == "move" for action in session.preview_actions)
        )

    def test_after_attack_current_root_prefers_escape_over_warm_approach(self):
        cells = [(x, 0, 0) for x in range(-1, 4)]
        edges = [(a, b) for a in cells for b in cells if abs(a[0] - b[0]) == 1]
        session = FakeNativeSession(spells=[], cells=cells, edges=edges)
        hint(session, [dict(type="move", path=[[1, 0, 0]])])
        with patch(
            "wakfu_ai.planning.query_search.attacked_this_turn", return_value=True
        ), patch(
            "wakfu_ai.planning.query_search.damaged_targets_this_turn",
            return_value=frozenset({9}),
        ):
            result = run_search(session)
        self.assertEqual(result["teamPosture"]["root"]["mode"], "retreat")
        self.assertEqual(result["action"]["type"], "move")
        self.assertLess(result["action"]["path"][-1][0], 0)


if __name__ == "__main__":
    unittest.main()
