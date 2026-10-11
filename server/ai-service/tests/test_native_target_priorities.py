"""Synthetic regressions for soft registered-summon target preference."""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest

_HERE = Path(__file__).resolve().parents[1]
_TESTS = _HERE / "tests"
for _path in (str(_HERE), str(_TESTS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from test_query_search import ENEMY_ID, fixture, run_search
from wakfu_ai.planning.query_search import _metrics, search
from wakfu_ai.planning.scoring import evaluate
from wakfu_ai.planning.tactical import DEFAULT_WEIGHTS
from wakfu_ai.planning.topology_distance import measure


def _combat_actor(identity, team, position, hp=30, *, registered_summon=False):
    actor = dict(
        id=identity,
        team=team,
        controlled=True,
        position=tuple(position),
        hp=hp,
        max_hp=30,
        armor=0,
        ap=6,
        mp=3,
        wp=2,
    )
    if registered_summon:
        actor["registeredSummon"] = True
    return actor


def _score_root(actors):
    return dict(
        actors=actors,
        position=0,
        threat=0,
        uncertainty=0,
        features={},
    )


class NativeTargetPriorityTests(unittest.TestCase):
    def test_player_is_preferred_for_equal_reachable_damage(self):
        root = _score_root(
            {
                1: _combat_actor(1, 1, (0, 0, 0)),
                2: _combat_actor(2, 0, (1, 0, 0)),
                3: _combat_actor(3, 0, (2, 0, 0), registered_summon=True),
            }
        )
        outcome = deepcopy(root)
        outcome["actors"][2]["hp"] -= 20
        outcome["actors"][3]["hp"] -= 20

        score, components, intent, target = evaluate(
            root,
            outcome,
            1,
            dict(DEFAULT_WEIGHTS),
            {},
            summon_value=0.25,
        )

        self.assertGreater(score, 0)
        self.assertEqual(components["damage"], 25.0)
        self.assertEqual(intent, "damage")
        self.assertEqual(target, 2)

    def test_registered_summon_kill_has_no_finish_bonus_against_small_player_hit(self):
        root = _score_root(
            {
                1: _combat_actor(1, 1, (0, 0, 0)),
                2: _combat_actor(2, 0, (1, 0, 0)),
                3: _combat_actor(3, 0, (2, 0, 0), hp=2, registered_summon=True),
            }
        )
        summon_kill = deepcopy(root)
        summon_kill["actors"][3]["hp"] = 0
        player_hit = deepcopy(root)
        player_hit["actors"][2]["hp"] -= 5

        summon_score, summon_components, _, _ = evaluate(
            root, summon_kill, 1, dict(DEFAULT_WEIGHTS), {}, summon_value=0.25
        )
        player_score, _, _, player_target = evaluate(
            root, player_hit, 1, dict(DEFAULT_WEIGHTS), {}, summon_value=0.25
        )

        self.assertEqual(summon_components["kills"], 0.0)
        self.assertGreater(summon_score, 0.0)
        self.assertGreater(player_score, summon_score)
        self.assertEqual(player_target, 2)

    def test_summon_remains_a_useful_only_target(self):
        spell = dict(
            spellId=701,
            level=1,
            casting=dict(levels=[[0, 3, []]], conditional=[]),
        )
        session = fixture([spell], effects={701: "damage"})
        enemy = next(
            row for row in session.root_state["actors"] if row["id"] == ENEMY_ID
        )
        enemy["hp"] = 5
        enemy["registeredSummon"] = True

        result = run_search(session)

        self.assertEqual(result["action"]["type"], "cast")
        self.assertEqual(result["action"]["targetId"], ENEMY_ID)
        self.assertTrue(
            any(
                next(row for row in state["public"]["actors"] if row["id"] == ENEMY_ID)[
                    "hp"
                ]
                == 0
                for state in session.states.values()
            )
        )

    def test_missing_flag_and_only_summon_targets_fall_back_to_full_topology(self):
        raw = dict(
            actors=[
                dict(id=1, team=1, hp=10, position=[0, 0, 0]),
                dict(id=2, team=0, hp=10, position=[2, 0, 0]),
            ],
            topologyDistances={"1": 2, "2": 2},
            topologyCellCount=4,
        )
        unflagged = _metrics(raw, 1)
        self.assertEqual(unflagged["position_basis"], "directed_xyz_topology")
        self.assertEqual(unflagged["position"], -0.5)

        cells = [(x, 0, 0) for x in range(3)]
        edges = [
            (cells[0], cells[1]),
            (cells[1], cells[0]),
            (cells[1], cells[2]),
            (cells[2], cells[1]),
        ]
        actors = [
            _combat_actor(1, 1, cells[0]),
            _combat_actor(2, 0, cells[2], registered_summon=True),
        ]
        measured = measure(cells, edges, actors, actor_id=1)
        self.assertEqual(measured["topologyDistances"]["1"], 2)
        metrics = _metrics(dict(actors=actors, **measured), 1)
        self.assertEqual(metrics["position_basis"], "directed_xyz_topology")
        self.assertEqual(metrics["position"], -0.5)

    def test_invalid_registered_summon_scales_are_rejected(self):
        for value in (True, -0.01, 1.01, math.nan, math.inf, "0.25"):
            with self.subTest(value=value):
                session = fixture([])
                session.envelope["policy"]["registeredSummonValue"] = value
                coroutine = search(session.envelope, session.store)
                with self.assertRaisesRegex(ValueError, "registered summon"):
                    next(coroutine)

    def test_primary_xyz_distance_keeps_blocking_construct_occupied(self):
        cells = [(x, 0, 0) for x in range(5)]
        edges = []
        for left, right in zip(cells, cells[1:]):
            edges.extend(((left, right), (right, left)))
        actors = [
            _combat_actor(1, 1, cells[0]),
            _combat_actor(2, 0, cells[2], registered_summon=True),
            _combat_actor(3, 1, cells[3]),  # Occupying construct blocks this cell.
            _combat_actor(4, 0, cells[4]),
        ]

        measured = measure(cells, edges, actors, actor_id=1)

        self.assertEqual(measured["topologyDistances"]["1"], 2)
        self.assertIsNone(measured["primaryTopologyDistances"]["1"])
        metrics = _metrics(dict(actors=actors, **measured), 1)
        self.assertEqual(
            metrics["position_basis"], "directed_xyz_primary_target_topology"
        )
        self.assertEqual(metrics["position"], -(len(cells) + 1) * 0.25)


if __name__ == "__main__":
    unittest.main()
