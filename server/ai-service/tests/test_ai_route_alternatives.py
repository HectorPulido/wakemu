"""Hazard-aware route alternatives preserve safe paths to shared cells."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wakfu_ai.planning.query_search import _movement_orders
from test_query_search import ACTOR_ID, actor


class AIRouteAlternativeTests(unittest.TestCase):
    def test_safe_route_to_shared_endpoint_is_offered_before_hazard_route(self):
        origin = (0, 0, 0)
        hazard = (0, 1, 0)
        safe = (1, 0, 0)
        shared = (1, 1, 0)
        enemy = (2, 1, 0)
        edges = [
            (origin, hazard),
            (origin, safe),
            (hazard, shared),
            (safe, shared),
            (shared, enemy),
        ]
        cells = {origin, hazard, safe, shared, enemy}
        actors = {
            ACTOR_ID: actor(ACTOR_ID, 1, origin, mp=2),
            9: actor(9, 0, enemy),
        }

        route_orders = _movement_orders(
            edges,
            cells,
            actors,
            ACTOR_ID,
            hazard_cells={hazard},
        )
        routes = list(route_orders[0])
        safe_route = (safe, shared)
        hazard_route = (hazard, shared)

        self.assertIn(safe_route, routes)
        self.assertIn(hazard_route, routes)
        self.assertLess(routes.index(safe_route), routes.index(hazard_route))
        self.assertTrue(all(len(route) <= actors[ACTOR_ID]["mp"] for route in routes))
        self.assertTrue(
            all(
                edge in edges
                for route in routes
                for edge in zip((origin,) + route, route)
            )
        )

    def test_longer_safe_detour_is_retained_only_within_mp_and_unoccupied_edges(self):
        origin = (0, 0, 0)
        hazard = (1, 0, 0)
        safe1 = (0, 1, 0)
        safe2 = (1, 1, 0)
        safe3 = (2, 1, 0)
        end = (2, 0, 0)
        enemy = (3, 0, 0)
        edges = [
            (origin, hazard),
            (hazard, end),
            (origin, safe1),
            (safe1, safe2),
            (safe2, safe3),
            (safe3, end),
            (end, enemy),
        ]
        cells = {origin, hazard, safe1, safe2, safe3, end, enemy}
        actors = {
            ACTOR_ID: actor(ACTOR_ID, 1, origin, mp=4),
            9: actor(9, 0, enemy),
        }

        routes = list(
            _movement_orders(edges, cells, actors, ACTOR_ID, hazard_cells={hazard})[0]
        )
        safe_route = (safe1, safe2, safe3, end)
        hazard_route = (hazard, end)
        self.assertIn(safe_route, routes)
        self.assertLess(routes.index(safe_route), routes.index(hazard_route))
        self.assertTrue(all(len(route) <= actors[ACTOR_ID]["mp"] for route in routes))
        self.assertTrue(
            all(
                edge in edges
                for route in routes
                for edge in zip((origin,) + route, route)
            )
        )

        actors[2] = actor(2, 1, safe1)
        blocked_routes = list(
            _movement_orders(edges, cells, actors, ACTOR_ID, hazard_cells={hazard})[0]
        )
        self.assertNotIn(safe_route, blocked_routes)
        self.assertIn(hazard_route, blocked_routes)

        del actors[2]
        actors[ACTOR_ID]["mp"] = 3
        short_budget_routes = list(
            _movement_orders(edges, cells, actors, ACTOR_ID, hazard_cells={hazard})[0]
        )
        self.assertNotIn(safe_route, short_budget_routes)

    def test_no_hazard_keeps_original_shortest_route_stream(self):
        cells = [(x, 0, 0) for x in range(4)]
        edges = []
        for left, right in zip(cells, cells[1:]):
            edges.extend(((left, right), (right, left)))
        actors = {
            ACTOR_ID: actor(ACTOR_ID, 1, cells[0], mp=2),
            9: actor(9, 0, cells[3]),
        }

        routes = list(_movement_orders(edges, cells, actors, ACTOR_ID)[0])

        self.assertEqual(
            routes,
            [((1, 0, 0), (2, 0, 0)), ((1, 0, 0),)],
        )


if __name__ == "__main__":
    unittest.main()
