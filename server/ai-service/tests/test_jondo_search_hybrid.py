"""Beam allocation for preparation outcomes certified by native previews."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_query_search import FakeNativeSession, actor, run_search
from wakfu_ai.planning.query_search import _diverse_beam


class PreparationSession(FakeNativeSession):
    def __init__(self, *, resource_setup=False):
        self.resource_setup = resource_setup
        super().__init__(
            spells=[],
            cells=[(0, 0, 0)],
            edges=[],
            outcome_features={"owned_state_progress": 0},
        )
        self.root_state["actors"] = [actor(1, 1, (0, 0, 0), ap=6, mp=0)] + [
            actor(identity, 0, (identity, 0, 0), ap=0, mp=0) for identity in (9, 10, 11)
        ]
        self.envelope["policy"]["limits"].update(
            depth=2, beam=2, nodes=16, probeQuantum=8
        )
        self.root_state["stage"] = "root"

    def request(self, query):
        if query["operation"] != "preview":
            return super().request(query)
        self.preview_actions.append(deepcopy(query["action"]))
        previous = self.states[query["state"]]["public"]
        public = deepcopy(previous)
        action = query["action"]
        public["key"] = "state-" + str(len(self.states))
        public["stateRevision"] += len(self.states)
        public["actors"][0]["ap"] -= 2 if action["spellId"] == 50 else 1
        public["stage"] = "finished"
        if action["spellId"] == 50:
            public["stage"] = "prepared"
            if self.resource_setup:
                public["actors"][0]["ap"] += 4
            else:
                public["outcomeFeatures"]["owned_state_progress"] = 1
        else:
            target = next(
                row for row in public["actors"] if row["id"] == action["targetId"]
            )
            target["hp"] -= 20 if action["spellId"] == 51 else 2
        self.states[public["key"]] = dict(public=public, used=False)
        return dict(id=query["id"], supported=True, result=public)


def scenario_candidates(graph, state, repertoire, actor_id, *args, **kwargs):
    if state["stage"] == "root":
        for identity in (9, 10, 11):
            yield dict(
                type="cast",
                spellId=identity,
                level=1,
                targetId=identity,
                target=[identity, 0, 0],
            )
        yield dict(type="cast", spellId=50, level=1, targetId=1, target=[0, 0, 0])
    elif state["stage"] == "prepared":
        yield dict(type="cast", spellId=51, level=1, targetId=9, target=[9, 0, 0])


class ThreeStepPreparationSession(PreparationSession):
    def __init__(self, *, resource_setup=False):
        super().__init__(resource_setup=resource_setup)
        self.envelope["policy"]["limits"]["depth"] = 3

    def request(self, query):
        if query["operation"] != "preview":
            return super().request(query)
        if query["action"]["type"] == "move":
            self.preview_actions.append(deepcopy(query["action"]))
            public = deepcopy(self.states[query["state"]]["public"])
            public.update(key="state-" + str(len(self.states)), stage="moved")
            public["actors"][0]["position"] = [1, 0, 0]
            self.states[public["key"]] = dict(public=public, used=False)
            return dict(id=query["id"], supported=True, result=public)
        response = super().request(query)
        if query["action"]["spellId"] != 50:
            public = response["result"]
            public["outcomeFeatures"]["owned_state_progress"] = 0
            public["actors"][0]["ap"] = min(5, public["actors"][0]["ap"])
        return response


def three_step_candidates(graph, state, repertoire, actor_id, *args, **kwargs):
    if state["stage"] == "prepared":
        for identity in (9, 10, 11):
            yield dict(
                type="cast",
                spellId=identity,
                level=1,
                targetId=identity,
                target=[identity, 0, 0],
            )
        yield dict(type="move", path=[[1, 0, 0]])
    elif state["stage"] == "moved":
        yield dict(type="cast", spellId=51, level=1, targetId=9, target=[9, 0, 0])
    else:
        yield from scenario_candidates(graph, state, repertoire, actor_id)


class HybridSearchTests(unittest.TestCase):
    def test_unspent_preparation_survives_intervening_movement(self):
        for resource_setup in (False, True):
            with self.subTest(resource_setup=resource_setup):
                session = ThreeStepPreparationSession(resource_setup=resource_setup)
                progress = []

                def record_beam(options, *args, **kwargs):
                    progress.extend(
                        (node["state"]["stage"], node.get("preparationProgress", 0))
                        for node in options
                    )
                    return _diverse_beam(options, *args, **kwargs)

                with patch(
                    "wakfu_ai.planning.query_search.candidates", three_step_candidates
                ), patch("wakfu_ai.planning.query_search._diverse_beam", record_beam):
                    result = run_search(session)
                self.assertEqual(
                    [step["type"] for step in result["plan"]], ["cast", "move", "cast"]
                )
                self.assertEqual(result["action"]["spellId"], 50)
                self.assertEqual(result["components"]["damage"], 20)
                self.assertAlmostEqual(
                    result["score"], sum(result["components"].values())
                )
                self.assertTrue(
                    any(stage == "moved" and amount > 0 for stage, amount in progress)
                )
                self.assertTrue(
                    all(
                        amount == 0 for stage, amount in progress if stage == "finished"
                    )
                )

    def test_setup_without_useful_followup_does_not_win_final_selection(self):
        session = PreparationSession()

        def without_followup(graph, state, repertoire, actor_id, *args, **kwargs):
            if state["stage"] == "root":
                yield from scenario_candidates(graph, state, repertoire, actor_id)

        with patch("wakfu_ai.planning.query_search.candidates", without_followup):
            result = run_search(session)
        self.assertEqual(result["action"]["spellId"], 9)
        self.assertEqual(result["components"]["damage"], 2)

    def test_certified_ap_gain_keeps_followup_in_beam(self):
        session = PreparationSession(resource_setup=True)
        with patch("wakfu_ai.planning.query_search.candidates", scenario_candidates):
            result = run_search(session)
        self.assertEqual([step["spellId"] for step in result["plan"]], [50, 51])
        self.assertEqual(result["components"]["damage"], 20)
        self.assertNotIn("preparationProgress", result["components"])

    def test_preparation_survives_damage_crowding_without_score_bonus(self):
        session = PreparationSession()
        with patch("wakfu_ai.planning.query_search.candidates", scenario_candidates):
            result = run_search(session)
        self.assertEqual([step["spellId"] for step in result["plan"]], [50, 51])
        self.assertAlmostEqual(result["score"], sum(result["components"].values()))
        self.assertLessEqual(result["expanded"], 16)
        self.assertEqual(result["components"]["damage"], 20)

    def test_no_progress_does_not_displace_stronger_candidates(self):
        options = [
            dict(
                score=score,
                actions=[{}],
                key=str(score),
                intent="damage",
                target=score,
                preparationProgress=0,
                state={"key": str(score)},
            )
            for score in (4, 3, 2)
        ]
        selected = _diverse_beam(options, 2, 1)
        self.assertEqual([row["score"] for row in selected], [4, 3])

    def test_preparation_preserves_top_outcome_and_exact_state_diversity(self):
        options = [
            dict(
                score=score,
                actions=[{}],
                key=str(score),
                intent="damage",
                target=score,
                preparationProgress=progress,
                state={"key": str(score)},
            )
            for score, progress in ((4, 0), (3, 0), (-1, 2))
        ]
        self.assertEqual(
            [row["score"] for row in _diverse_beam(options, 2, 1)], [4, -1]
        )
        self.assertEqual([row["score"] for row in _diverse_beam(options, 1, 1)], [4])


if __name__ == "__main__":
    unittest.main()
