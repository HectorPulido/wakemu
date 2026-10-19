"""Bounded search should probe an in-range damage target before a weak distant one."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wakfu_ai.context.native_context import NativeGraph
from wakfu_ai.planning.query_search import candidates
from test_query_search import ACTOR_ID, ENEMY_ID, FakeNativeSession, actor, run_search


ADJACENT_ENEMY_ID = 8
SPELL_ID = 700


class RangeCheckingSession(FakeNativeSession):
    """Native preview fixture that rejects damage casts outside range 1."""

    def request(self, query):
        action = query.get("action", {})
        if query.get("operation") == "preview" and action.get("type") == "cast":
            public = self.states[query["state"]]["public"]
            caster = next(row for row in public["actors"] if row["id"] == ACTOR_ID)
            distance = abs(caster["position"][0] - action["target"][0]) + abs(
                caster["position"][1] - action["target"][1]
            )
            if distance != 1:
                self.preview_actions.append(deepcopy(action))
                return {
                    "id": query["id"],
                    "supported": False,
                    "unknownDependencies": ["native_range_rejected"],
                }
            response = super().request(query)
            if (
                response.get("supported")
                and action.get("targetId") == ADJACENT_ENEMY_ID
            ):
                target = next(
                    row
                    for row in response["result"]["actors"]
                    if row["id"] == ADJACENT_ENEMY_ID
                )
                target["hp"] = max(0, target["hp"] - 5)
            return response
        return super().request(query)


def spell_with_damage_range_hint():
    return dict(
        spellId=SPELL_ID,
        level=1,
        casting=dict(
            protected=False,
            maximum_level=1,
            line_of_sight=True,
            linear=False,
            free_cell=False,
            levels=[[1, 1, []]],
            costs=[[3, 0, 0]],
            categories=[],
            conditional=[],
        ),
        advisoryCapabilities=dict(
            spellId=SPELL_ID,
            level=1,
            tags=["damage"],
        ),
    )


def session_with_competing_enemies():
    cells = [[x, 0, 0] for x in range(7)] + [[0, 0, 1]]
    edges = [((x, 0, 0), (x + 1, 0, 0)) for x in range(6)]
    edges += [(end, start) for start, end in edges]
    session = RangeCheckingSession(
        spells=[spell_with_damage_range_hint()],
        cells=cells,
        edges=edges,
        effects={SPELL_ID: "damage"},
    )
    session.root_actors[0]["mp"] = 0
    session.root_actors[0]["hp"] = 100
    session.root_actors[0]["max_hp"] = 100
    session.root_actors[2]["position"] = [6, 0, 0]
    session.root_actors[2]["hp"] = 1
    session.root_actors.append(actor(ADJACENT_ENEMY_ID, 0, (1, 0, 0), hp=100))
    session.root_state["actors"] = deepcopy(session.root_actors)
    session.envelope["root"]["actors"] = session.root_state["actors"]
    session.envelope["policy"]["limits"].update(nodes=1, depth=1)
    return session


class RangeProbeOrderingTests(unittest.TestCase):
    def test_one_preview_budget_probes_in_range_enemy_before_far_low_hp_target(self):
        session = session_with_competing_enemies()

        result = run_search(session)

        self.assertEqual(len(session.preview_actions), 1)
        self.assertEqual(session.preview_actions[0]["type"], "cast")
        self.assertEqual(session.preview_actions[0]["targetId"], ADJACENT_ENEMY_ID)
        self.assertEqual(result["action"]["type"], "cast")
        self.assertEqual(result["action"]["targetId"], ADJACENT_ENEMY_ID)

    def test_range_ordering_retains_far_target_and_full_candidate_corpus(self):
        session = session_with_competing_enemies()
        state = deepcopy(session.root_state)
        graph = NativeGraph(session.root_graph)
        spell = spell_with_damage_range_hint()
        baseline = dict(spell)
        baseline.pop("advisoryCapabilities")
        before = list(candidates(graph, state, {"spells": [baseline]}, ACTOR_ID))
        after = list(candidates(graph, state, {"spells": [spell]}, ACTOR_ID))

        self.assertEqual(
            Counter(json.dumps(action, sort_keys=True) for action in before),
            Counter(json.dumps(action, sort_keys=True) for action in after),
        )
        self.assertIn(
            dict(
                type="cast",
                spellId=SPELL_ID,
                level=1,
                target=[6, 0, 0],
                targetId=ENEMY_ID,
            ),
            after,
        )

    def test_conditional_range_branch_keeps_far_target_in_known_range(self):
        session = session_with_competing_enemies()
        spell = spell_with_damage_range_hint()
        spell["casting"]["conditional"] = [dict(ranges=[[1, 6]])]
        actions = list(
            candidates(
                NativeGraph(session.root_graph),
                deepcopy(session.root_state),
                {"spells": [spell]},
                ACTOR_ID,
            )
        )
        first_cast = next(action for action in actions if action["type"] == "cast")

        self.assertEqual(first_cast["targetId"], ENEMY_ID)
        self.assertEqual(first_cast["target"], [6, 0, 0])

    def test_xy_distance_zero_remains_an_in_range_ordering_case(self):
        session = RangeCheckingSession(
            spells=[spell_with_damage_range_hint()],
            cells=[[x, 0, 0] for x in range(7)] + [[0, 0, 1]],
            edges=[],
            effects={SPELL_ID: "damage"},
        )
        session.root_actors[0]["mp"] = 0
        session.root_actors[2]["position"] = [6, 0, 0]
        session.root_state["actors"] = deepcopy(session.root_actors)
        session.envelope["root"]["actors"] = session.root_state["actors"]
        actions = list(
            candidates(
                NativeGraph(session.root_graph),
                deepcopy(session.root_state),
                {"spells": [spell_with_damage_range_hint()]},
                ACTOR_ID,
            )
        )
        self.assertTrue(
            any(
                action.get("targetId") == ACTOR_ID and action.get("target") == [0, 0, 0]
                for action in actions
            )
        )
        self.assertTrue(
            any(
                action.get("targetId") == ENEMY_ID and action.get("target") == [6, 0, 0]
                for action in actions
            )
        )


if __name__ == "__main__":
    unittest.main()
