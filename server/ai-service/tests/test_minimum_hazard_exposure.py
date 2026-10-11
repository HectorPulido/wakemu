"""Regression coverage for unavoidable hazard entries on directed topology."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_ai.planning.topology_distance import directed_adjacencies, minimum_exposure
from wakfu_ai.planning.query_search import _movement_orders
from wakfu_ai.context.native_context import encode
from test_query_search import ACTOR_ID, ALLY_ID, actor, fixture, run_search


class MinimumHazardExposureTests(unittest.TestCase):
    def test_weighted_zero_one_path_respects_direction_and_height(self):
        origin = (0, 0, 0)
        lower = (1, 0, 0)
        upper = (1, 0, 1)
        goal = (2, 0, 1)
        _, reverse = directed_adjacencies(
            [(origin, lower), (origin, upper), (upper, goal)]
        )

        # The lower hazard is a tempting short branch, but the directed upper
        # route reaches the goal with no hazard exposure.
        self.assertEqual(minimum_exposure(reverse, {goal}, set(), origin, {lower}), 0)
        # With the safe branch removed, entering the upper hazard costs one.
        _, forced_reverse = directed_adjacencies([(origin, upper), (upper, goal)])
        self.assertEqual(
            minimum_exposure(forced_reverse, {goal}, set(), origin, {upper}), 1
        )
        # Reverse movement is not inferred from the graph.
        self.assertIsNone(
            minimum_exposure(forced_reverse, {origin}, set(), goal, {upper})
        )

    def test_occupied_corridor_is_unreachable_and_multiple_goals_choose_best(self):
        origin, bridge, left, right = ((0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 1, 0))
        _, reverse = directed_adjacencies(
            [(origin, bridge), (bridge, left), (origin, right)]
        )
        self.assertIsNone(minimum_exposure(reverse, {left}, {bridge}, origin, {bridge}))
        self.assertEqual(
            minimum_exposure(reverse, {left, right}, set(), origin, {bridge}), 0
        )

    def test_no_hazards_and_origin_goal_have_zero_exposure(self):
        origin, step, goal = (0, 0, 0), (0, 1, 0), (0, 2, 0)
        _, reverse = directed_adjacencies([(origin, step), (step, goal)])
        self.assertEqual(minimum_exposure(reverse, {goal}, set(), origin, set()), 0)
        self.assertEqual(
            minimum_exposure(reverse, {origin}, set(), origin, {origin}), 0
        )

    def test_required_border_bridge_remains_a_planner_move(self):
        session = fixture(
            [],
            edges=[
                ((0, 0, 0), (1, 0, 0)),
                ((1, 0, 0), (2, 0, 0)),
                ((2, 0, 0), (3, 0, 0)),
            ],
        )
        session.root_state["actors"] = [
            actor(ACTOR_ID, 1, (0, 0, 0)),
            actor(ALLY_ID, 1, (0, 0, 1)),
            actor(9, 0, (3, 0, 0)),
        ]
        graph = encode(
            {
                "runtime": SimpleNamespace(
                    fight=SimpleNamespace(
                        walkable=frozenset(tuple(cell) for cell in session.cells),
                        edges=frozenset((tuple(a), tuple(b)) for a, b in session.edges),
                        native_border_cells=frozenset({(1, 0, 0)}),
                    )
                )
            }
        )
        session.root_state["nativeContext"] = session.store.put_json(graph)
        session.envelope["root"] = session.root_state
        session.envelope["policy"]["limits"]["depth"] = 1
        bridge_move = {"type": "move", "path": [[1, 0, 0]]}

        def only_bridge_move(*args, **kwargs):
            yield bridge_move

        with patch(
            "wakfu_ai.planning.query_search.candidates", side_effect=only_bridge_move
        ):
            result = run_search(session)

        self.assertEqual(result["action"], bridge_move)
        self.assertEqual(result["components"]["battleground_border_exposure"], 0)

    def test_required_bridge_precedes_safe_dead_end_in_candidate_order(self):
        origin, bridge, enemy_approach, enemy, dead_end = (
            (0, 0, 0),
            (1, 0, 0),
            (2, 0, 0),
            (3, 0, 0),
            (0, 1, 0),
        )
        actors = {
            ACTOR_ID: actor(ACTOR_ID, 1, origin, mp=1),
            9: actor(9, 0, enemy),
        }
        orders = _movement_orders(
            [
                (origin, bridge),
                (bridge, enemy_approach),
                (enemy_approach, enemy),
                (origin, dead_end),
            ],
            {origin, bridge, enemy_approach, enemy, dead_end},
            actors,
            ACTOR_ID,
            hazard_cells={bridge},
        )
        self.assertEqual(next(orders[0]), (bridge,))


if __name__ == "__main__":
    unittest.main()
