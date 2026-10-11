"""Registered native perimeter is a conservative route preference, not a ban."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_ai.context.native_context import NativeGraph, encode
from wakfu_ai.planning.turn_memory import battleground_border_cells
from wakfu_ai.planning.query_search import _movement_orders
from test_query_search import actor, fixture, run_search, ACTOR_ID, ENEMY_ID


class NativeBorderRoutingTests(unittest.TestCase):
    def graph(self, **fields):
        graph = NativeGraph(
            encode({"runtime": SimpleNamespace(fight=SimpleNamespace(**fields))})
        )
        runtime = graph.field(graph.data["root"], "runtime")
        return graph, graph.field(runtime, "fight")

    def test_only_registered_native_coordinates_supply_border(self):
        graph, fight = self.graph(
            native_border_cells={(18, -40, 2), (0, 1, 0)}, map_id=999, spell_id=700
        )
        self.assertEqual(
            battleground_border_cells(graph, fight),
            frozenset({(18, -40, 2), (0, 1, 0)}),
        )
        graph, fight = self.graph(map_id=999, spell_id=700)
        self.assertEqual(battleground_border_cells(graph, fight), frozenset())

    def test_safe_route_precedes_shorter_dangerous_route(self):
        origin, dangerous, safe1, safe2, enemy = (
            (0, 0, 0),
            (1, 0, 0),
            (0, 1, 0),
            (1, 1, 0),
            (2, 0, 0),
        )
        actors = {
            ACTOR_ID: actor(ACTOR_ID, 1, origin),
            ENEMY_ID: actor(ENEMY_ID, 0, enemy),
        }
        orders = _movement_orders(
            [(origin, dangerous), (origin, safe1), (safe1, safe2)],
            [origin, dangerous, safe1, safe2, enemy],
            actors,
            ACTOR_ID,
            hazard_cells={dangerous},
        )
        routes = list(orders[0])
        self.assertLess(routes.index((safe1, safe2)), routes.index((dangerous,)))
        self.assertIn((dangerous,), routes)

    def test_only_dangerous_route_remains_eligible(self):
        origin, dangerous, enemy = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        actors = {
            ACTOR_ID: actor(ACTOR_ID, 1, origin),
            ENEMY_ID: actor(ENEMY_ID, 0, enemy),
        }
        orders = _movement_orders(
            [(origin, dangerous)],
            [origin, dangerous, enemy],
            actors,
            ACTOR_ID,
            hazard_cells={dangerous},
        )
        self.assertEqual(list(orders[0]), [(dangerous,)])

    def test_actual_search_exposes_border_penalty_without_forbidding_move(self):
        session = fixture([], effects={701: "damage"})
        graph = encode(
            {
                "runtime": SimpleNamespace(
                    fight=SimpleNamespace(
                        walkable=frozenset(tuple(c) for c in session.cells),
                        edges=frozenset((tuple(a), tuple(b)) for a, b in session.edges),
                        native_border_cells=frozenset({(1, 0, 0)}),
                    )
                )
            }
        )
        session.root_state["nativeContext"] = session.store.put_json(graph)
        session.envelope["policy"]["limits"]["depth"] = 2
        move = dict(type="move", path=[[1, 0, 0]])
        cast = dict(
            type="cast", spellId=701, level=1, target=[3, 0, 0], targetId=ENEMY_ID
        )

        def choices(graph, state, repertoire, actor_id, *args, **kwargs):
            current = next(a for a in state["actors"] if a["id"] == ACTOR_ID)
            if current["position"] == [0, 0, 0]:
                yield move
            else:
                yield cast

        with patch("wakfu_ai.planning.query_search.candidates", side_effect=choices):
            result = run_search(session)
        self.assertEqual(result["action"], move)
        self.assertEqual(result["components"]["battleground_border_exposure"], -2)
        self.assertEqual(result["components"]["damage"], 5)


if __name__ == "__main__":
    unittest.main()
