import unittest
from unittest.mock import patch

from wakfu_ai.context.native_context import NativeGraph, encode
from wakfu_ai.planning import query_search


def actor(identity, team, position, *, mp=0, registered_summon=False):
    return dict(
        id=identity,
        team=team,
        hp=20,
        max_hp=20,
        ap=0,
        mp=mp,
        wp=0,
        position=position,
        registeredSummon=registered_summon,
    )


class MovementTargetDiversityTests(unittest.TestCase):
    def setUp(self):
        self.origin = (0, 0, 0)
        self.beacon = (1, 0, 0)
        self.player = (0, 6, 0)
        self.left = (-1, 0, 0)
        self.up = (0, 1, 0)
        self.cells = {
            self.origin,
            self.beacon,
            self.player,
            self.left,
            *[(0, y, 0) for y in range(1, 6)],
        }
        edges = set()
        for first, second in (
            (self.origin, self.beacon),
            (self.origin, self.left),
            *[((0, y, 0), (0, y + 1, 0)) for y in range(6)],
        ):
            edges.add((first, second))
            edges.add((second, first))
        self.edges = edges
        self.actors = {
            1: actor(1, 1, self.origin, mp=1),
            # This native roster fact is not used to discard or penalize the
            # actor. It models a nearby registered summon alongside a player.
            33: actor(33, 0, self.beacon, registered_summon=True),
            6: actor(6, 0, self.player),
        }

    def test_near_summon_does_not_starve_route_to_farther_player(self):
        orders = query_search._movement_orders(
            list(self.edges), self.cells, self.actors, 1
        )

        # The global ordering still promotes its original best route. The
        # next streams explicitly represent each rival, including the farther
        # player, so a narrow search budget sees both destinations.
        representatives = [next(order, None) for order in orders]
        self.assertEqual(representatives[0], (self.left,))
        self.assertEqual(representatives[1], (self.up,))
        self.assertEqual(representatives[2], (self.left,))

        # The complete original movement stream is retained; this is only
        # ordering diversity, not a legality filter or destination whitelist.
        original_routes = {representatives[0], *orders[0]}
        self.assertEqual(original_routes, {(self.left,), (self.up,)})

        graph = NativeGraph(
            encode(
                {
                    "runtime": {
                        "fight": {
                            "turn_id": 0,
                            "events": [],
                            "native_border_cells": [],
                        }
                    },
                    "edges": list(self.edges),
                }
            )
        )
        stream = query_search._movement_candidates(
            graph,
            graph.field(graph.data["root"], "edges"),
            self.cells,
            self.actors,
            1,
            geometry=lambda _: list(self.edges),
        )
        first, second = next(stream), next(stream)
        self.assertEqual(first["path"], [list(self.left)])
        self.assertEqual(second["path"], [list(self.up)])

    def test_deadline_is_checked_before_each_representative_scan(self):
        with patch.object(
            query_search, "check", side_effect=[None, TimeoutError("expired")]
        ) as deadline_check:
            with self.assertRaisesRegex(TimeoutError, "expired"):
                query_search._movement_orders(
                    list(self.edges), self.cells, self.actors, 1
                )
        self.assertEqual(deadline_check.call_count, 2)

    def test_no_rivals_keeps_the_original_complete_route_stream(self):
        allies = {1: self.actors[1]}
        orders = query_search._movement_orders(list(self.edges), self.cells, allies, 1)
        self.assertEqual(len(orders), 1)
        self.assertEqual(set(orders[0]), {(self.left,), (self.up,), (self.beacon,)})


if __name__ == "__main__":
    unittest.main()
