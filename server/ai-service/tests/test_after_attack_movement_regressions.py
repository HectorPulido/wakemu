"""Behavioral movement regressions for post-attack approach and hazards."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wakfu_ai.context.native_context import encode
from wakfu_ai.planning.query_search import _movement_orders
from test_query_search import FakeNativeSession, actor, run_search


def line(cells):
    edges = []
    for left, right in zip(cells, cells[1:]):
        edges.extend(((left, right), (right, left)))
    return edges


class GlyphTollSession(FakeNativeSession):
    """Native preview fixture for explicit HP and MP tolls at x=1."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.certified_moves = []

    def request(self, query):
        prior = self.states.get(query.get("state"), {}).get("public", {})
        prior_actor = next(
            (row for row in prior.get("actors", ()) if row["id"] == 1), None
        )
        response = super().request(query)
        if (
            query.get("operation") == "preview"
            and query.get("action", {}).get("type") == "move"
            and response.get("supported")
        ):
            public = response["result"]
            mover = next(row for row in public["actors"] if row["id"] == 1)
            path = query["action"]["path"]
            crosses_glyph = [1, 0, 0] in path
            mp_cost = len(path) + (self.glyph_extra_mp_toll if crosses_glyph else 0)
            if mp_cost > prior_actor["mp"]:
                return {
                    "id": response["id"],
                    "supported": False,
                    "unknownDependencies": ["movement_mp_toll_exceeds_budget"],
                }
            mover["mp"] = prior_actor["mp"] - mp_cost
            if crosses_glyph:
                mover["hp"] -= self.glyph_hp_toll
                if mover["hp"] <= 0:
                    public["currentId"] = None
            self.certified_moves.append(
                dict(
                    path=[list(cell) for cell in path],
                    hp=mover["hp"],
                    mp=mover["mp"],
                )
            )
        return response


def install_committed_damage_ledger(session, target_id):
    events = [
        dict(kind="damage", source_id=1, target_id=target_id, amount=1),
        dict(kind="npc_cast", actor_id=1, turn_id=4, target_id=target_id),
    ]
    fight = SimpleNamespace(
        walkable=frozenset(tuple(cell) for cell in session.cells),
        edges=frozenset((tuple(a), tuple(b)) for a, b in session.edges),
        turn_id=4,
        events=events,
        native_border_cells=(),
    )
    graph = encode({"runtime": SimpleNamespace(fight=fight)})
    graph_key = session.store.put_json(graph)
    session.root_state["nativeContext"] = graph_key
    session.envelope["root"]["nativeContext"] = graph_key


class AfterAttackMovementRegressions(unittest.TestCase):
    def test_after_attack_actor_out_of_range_still_approaches_enemy(self):
        cells = [(x, 0, 0) for x in range(-2, 7)]
        actors = {
            1: actor(1, 1, (0, 0, 0), hp=30, mp=4),
            2: actor(2, 1, (-2, 0, 0)),
            9: actor(9, 0, (6, 0, 0)),
        }

        orders = _movement_orders(line(cells), cells, actors, 1, team_posture=True)
        chosen_route = next(orders[0])

        self.assertLess(
            abs(chosen_route[-1][0] - 6),
            abs(actors[1]["position"][0] - 6),
            "an out-of-range actor should close distance after its prior attack",
        )

    def test_after_attack_retreat_keeps_safe_route_ahead_of_glyph_route(self):
        cells = [(x, 0, 0) for x in range(-3, 3)]
        actors = {
            1: actor(1, 1, (0, 0, 0), hp=30, mp=1),
            2: actor(2, 1, (-3, 0, 0)),
            9: actor(9, 0, (2, 0, 0)),
        }
        glyph = {(1, 0, 0)}

        orders = _movement_orders(
            line(cells),
            cells,
            actors,
            1,
            retreat=True,
            hazard_cells=glyph,
        )
        chosen_route = next(orders[0])

        self.assertNotIn(chosen_route[-1], glyph)

    def test_healthy_actor_spends_full_mp_to_cross_toll_glyph_and_approach(self):
        cells = [(x, 0, 0) for x in range(7)]
        session = GlyphTollSession(spells=[], cells=cells, edges=line(cells))
        session.glyph_hp_toll = 1
        session.glyph_extra_mp_toll = 0
        session.root_actors[0]["hp"] = 100
        session.root_actors[0]["max_hp"] = 100
        session.root_actors[0]["mp"] = 4
        session.root_actors[2]["position"] = [6, 0, 0]
        session.root_state["actors"] = session.root_actors
        session.envelope["root"]["actors"] = session.root_actors

        result = run_search(session)

        self.assertEqual(result["action"]["type"], "move")
        self.assertEqual(result["plan"][-1]["path"][-1], [4, 0, 0])
        self.assertEqual(result["components"]["strategic_approach"], 2.0)

    def test_three_steps_plus_one_mp_glyph_tax_fits_four_mp_budget(self):
        cells = [(x, 0, 0) for x in range(7)]
        session = GlyphTollSession(spells=[], cells=cells, edges=line(cells))
        session.glyph_hp_toll = 0
        session.glyph_extra_mp_toll = 1
        session.root_actors[0]["hp"] = 100
        session.root_actors[0]["max_hp"] = 100
        session.root_actors[0]["mp"] = 4
        session.root_actors[2]["position"] = [6, 0, 0]
        session.root_state["actors"] = session.root_actors
        session.envelope["root"]["actors"] = session.root_actors

        result = run_search(session)

        self.assertEqual(result["action"]["type"], "move")
        self.assertEqual(result["plan"][-1]["path"][-1], [3, 0, 0])

    def test_native_lethal_glyph_toll_is_not_selected(self):
        cells = [(x, 0, 0) for x in range(7)]
        session = GlyphTollSession(spells=[], cells=cells, edges=line(cells))
        session.glyph_hp_toll = 25
        session.glyph_extra_mp_toll = 0
        session.root_actors[0]["hp"] = 25
        session.root_actors[0]["max_hp"] = 25
        session.root_actors[0]["mp"] = 4
        session.root_actors[2]["position"] = [6, 0, 0]
        session.root_state["actors"] = session.root_actors
        session.envelope["root"]["actors"] = session.root_actors

        result = run_search(session)

        self.assertFalse(
            result["action"].get("type") == "move"
            and [1, 0, 0] in result["action"].get("path", [])
        )

    def test_costly_nonlethal_glyph_toll_is_not_selected(self):
        cells = [(x, 0, 0) for x in range(7)]
        session = GlyphTollSession(spells=[], cells=cells, edges=line(cells))
        session.glyph_hp_toll = 25
        session.glyph_extra_mp_toll = 0
        session.root_actors[0]["hp"] = 100
        session.root_actors[0]["max_hp"] = 100
        session.root_actors[0]["mp"] = 4
        session.root_actors[2]["position"] = [6, 0, 0]
        session.root_state["actors"] = session.root_actors
        session.envelope["root"]["actors"] = session.root_actors

        result = run_search(session)

        self.assertFalse(
            result["action"].get("type") == "move"
            and [1, 0, 0] in result["action"].get("path", [])
        )

    def test_full_search_uses_four_mp_and_hp_toll_after_dead_beacon_attack(self):
        cells = [(x, 0, 0) for x in range(7)]
        session = GlyphTollSession(spells=[], cells=cells, edges=line(cells))
        session.glyph_hp_toll = 1
        session.glyph_extra_mp_toll = 0
        session.root_actors[0]["hp"] = 100
        session.root_actors[0]["max_hp"] = 100
        session.root_actors[0]["mp"] = 4
        session.root_actors[2]["position"] = [6, 0, 0]
        session.root_actors.append(
            dict(
                id=10,
                team=0,
                controlled=False,
                position=[1, 0, 0],
                hp=0,
                max_hp=10,
                armor=0,
                ap=0,
                mp=0,
                wp=0,
                registeredSummon=True,
            )
        )
        session.root_state["actors"] = session.root_actors
        session.envelope["root"]["actors"] = session.root_actors
        install_committed_damage_ledger(session, 10)

        result = run_search(session)

        self.assertEqual(result["action"]["type"], "move")
        self.assertEqual(result["action"]["path"][-1], [4, 0, 0])
        self.assertEqual(len(result["action"]["path"]), 4)
        self.assertIn(
            dict(path=[[1, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0]], hp=99, mp=0),
            session.certified_moves,
        )

    def test_committed_damage_to_live_primary_enemy_does_not_approach(self):
        cells = [(x, 0, 0) for x in range(-4, 7)]
        session = FakeNativeSession(spells=[], cells=cells, edges=line(cells))
        session.root_actors[0]["mp"] = 4
        session.root_actors[2]["position"] = [6, 0, 0]
        session.root_state["actors"] = session.root_actors
        session.envelope["root"]["actors"] = session.root_actors
        install_committed_damage_ledger(session, 9)

        result = run_search(session)

        self.assertEqual(result["teamPosture"]["root"]["mode"], "retreat")
        self.assertFalse(
            result["action"].get("type") == "move"
            and result["action"].get("path", [])[-1][0] > 0
        )

    def test_committed_kill_of_dead_beacon_does_not_block_primary_approach(self):
        cells = [(x, 0, 0) for x in range(-4, 7)]
        session = FakeNativeSession(spells=[], cells=cells, edges=line(cells))
        session.root_actors[0]["mp"] = 4
        session.root_actors[2]["position"] = [6, 0, 0]
        session.root_actors.append(
            dict(
                id=10,
                team=0,
                controlled=False,
                position=[1, 0, 0],
                hp=0,
                max_hp=10,
                armor=0,
                ap=0,
                mp=0,
                wp=0,
                registeredSummon=True,
            )
        )
        session.root_state["actors"] = session.root_actors
        session.envelope["root"]["actors"] = session.root_actors
        install_committed_damage_ledger(session, 10)

        result = run_search(session)

        self.assertEqual(result["action"]["type"], "move")
        self.assertGreater(result["action"]["path"][-1][0], 0)


if __name__ == "__main__":
    unittest.main()
