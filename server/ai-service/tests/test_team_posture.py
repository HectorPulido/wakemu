"""One actor changes its assignment with team geometry and native risk."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wakfu_ai.planning.team_posture import decide, contradicted_hold
from test_query_search import FakeNativeSession, actor, run_search


def fixture():
    cells = [(x, 0, 0) for x in range(4)] + [(1, 1, 0), (1, 2, 0)]
    pairs = [
        (cells[0], cells[1]),
        (cells[1], cells[2]),
        (cells[2], cells[3]),
        (cells[1], cells[4]),
        (cells[4], cells[5]),
    ]
    edges = pairs + [(end, start) for start, end in pairs]
    adjacency = {}
    for start, end in edges:
        adjacency.setdefault(start, set()).add(end)
    actors = {
        1: actor(1, 1, (1, 0, 0), hp=100, max_hp=100),
        2: actor(2, 1, (3, 0, 0)),
        9: actor(9, 0, (0, 0, 0), mp=3),
    }
    return actors, adjacency, cells, edges


class TeamPostureTests(unittest.TestCase):
    def test_same_actor_changes_with_health_allies_and_effective_armor(self):
        actors, adjacency, _, _ = fixture()
        self.assertEqual(decide(actors, 1, adjacency)["mode"], "hold")
        actors[1]["hp"] = 5
        self.assertEqual(decide(actors, 1, adjacency)["mode"], "retreat")
        actors[1]["armor"] = 29
        self.assertEqual(decide(actors, 1, adjacency)["mode"], "retreat")
        actors[1]["armor"] = 30
        self.assertEqual(decide(actors, 1, adjacency)["mode"], "hold")
        actors[1]["armor"] = 50
        self.assertEqual(decide(actors, 1, adjacency)["mode"], "hold")
        actors[2]["hp"] = 0
        self.assertEqual(decide(actors, 1, adjacency)["reason"], "no_living_allies")

    def test_ally_presence_without_protection_does_not_assign_tank(self):
        actors, adjacency, _, _ = fixture()
        actors[2]["position"] = (90, 90, 0)
        self.assertEqual(
            decide(actors, 1, adjacency)["reason"], "holding_does_not_protect_allies"
        )

    def test_bypass_and_directed_edges_do_not_manufacture_protection(self):
        actors, adjacency, _, _ = fixture()
        adjacency[(0, 0, 0)].add((2, 0, 0))
        self.assertEqual(decide(actors, 1, adjacency)["mode"], "retreat")
        actors, adjacency, _, _ = fixture()
        adjacency[(1, 0, 0)].discard((2, 0, 0))
        self.assertEqual(decide(actors, 1, adjacency)["mode"], "retreat")

    def test_before_attack_keeps_approach_and_unknown_topology_not_protection(self):
        actors, adjacency, _, _ = fixture()
        actors[2]["hp"] = 0
        self.assertEqual(
            decide(actors, 1, adjacency, after_attack=False)["mode"], "approach"
        )
        actors[2]["hp"] = 30
        self.assertEqual(decide(actors, 1, None)["mode"], "retreat")

    def test_native_lethal_or_ally_damage_overrides_healthy_hold(self):
        actors, adjacency, _, _ = fixture()
        posture = decide(actors, 1, adjacency)
        self.assertEqual(
            contradicted_hold(actors, 1, posture, {"observedActorHpLoss": 100}),
            "native_response_exposes_lethal_damage",
        )
        self.assertEqual(
            contradicted_hold(actors, 1, posture, {"observedAllyHpLoss": {2: 2}}),
            "native_response_reaches_protected_ally",
        )
        self.assertIsNone(contradicted_hold(actors, 1, posture, {}))

    def test_search_vetoes_hold_bonus_when_rival_forecast_exposes_actor_or_ally(self):
        cases = (
            (
                {"observedActorHpLoss": 100, "observedAllyHpLoss": {}},
                "native_response_exposes_lethal_damage",
            ),
            (
                {"observedActorHpLoss": 0, "observedAllyHpLoss": {2: 2}},
                "native_response_reaches_protected_ally",
            ),
            (
                {"observedActorHpLoss": 0, "observedAllyHpLoss": {}},
                None,
            ),
        )
        for evidence, expected_reason in cases:
            with self.subTest(evidence=evidence):
                session = self.session()
                session.envelope["operations"] = ["project_turn"]

                def forecast(state, actor_id, store, weights, **kwargs):
                    if False:
                        yield None
                    return dict(
                        risk=0,
                        knownLowerBound=0,
                        complete=True,
                        rivals=[],
                        unknownDependencies=[],
                        **evidence,
                    )

                with patch(
                    "wakfu_ai.planning.query_search.attacked_this_turn",
                    return_value=True,
                ), patch("wakfu_ai.planning.query_threat.forecast", forecast):
                    result = run_search(session)

                self.assertEqual(result["teamPosture"]["root"]["mode"], "hold")
                self.assertEqual(
                    result["teamPosture"]["selected"]["mode"],
                    "retreat" if expected_reason else "hold",
                )
                self.assertEqual(
                    result["action"]["type"], "move" if expected_reason else "end_turn"
                )
                self.assertEqual(
                    result["rivalForecasts"][0]["postureRiskReason"], expected_reason
                )

    def session(self, *, low_hp=False):
        actors, _, cells, edges = fixture()
        if low_hp:
            actors[1]["hp"] = 5
        session = FakeNativeSession(spells=[], cells=cells, edges=edges)
        session.root_state["actors"] = deepcopy(list(actors.values()))
        return session

    def test_search_holds_protecting_cell_but_same_actor_retreats_when_wounded(self):
        with patch(
            "wakfu_ai.planning.query_search.attacked_this_turn", return_value=True
        ):
            held = run_search(self.session())
            fled = run_search(self.session(low_hp=True))
        self.assertEqual(held["action"]["type"], "end_turn")
        self.assertEqual(held["teamPosture"]["root"]["mode"], "hold")
        self.assertEqual(fled["action"]["type"], "move")
        self.assertEqual(fled["teamPosture"]["root"]["mode"], "retreat")

    def test_rejected_retreat_is_never_published_as_legal_movement(self):
        session = self.session(low_hp=True)
        session.reject_all = True
        with patch(
            "wakfu_ai.planning.query_search.attacked_this_turn", return_value=True
        ):
            result = run_search(session)
        self.assertEqual(result["action"]["type"], "end_turn")
        self.assertTrue(
            any(action["type"] == "move" for action in session.preview_actions)
        )

    def test_posture_does_not_filter_damage_or_healing_casts(self):
        session = self.session(low_hp=True)
        session.spells = [{"spellId": 1, "level": 1}, {"spellId": 2, "level": 1}]
        session.effects = {1: "damage", 2: "heal"}
        session.root_state["actors"][1]["hp"] = 10
        with patch(
            "wakfu_ai.planning.query_search.attacked_this_turn", return_value=True
        ):
            result = run_search(session)
        self.assertTrue(any(action["type"] == "cast" for action in result["plan"]))
        self.assertEqual(
            {a["spellId"] for a in session.preview_actions if a["type"] == "cast"},
            {1, 2},
        )


if __name__ == "__main__":
    unittest.main()
