import random
import unittest

from wakfu_server.maps.monster_wander import (
    choose_step,
    group_neighbor_index,
    nearest_group,
    plan_group_path,
)


class DispersionTests(unittest.TestCase):
    def test_neighbor_scope_and_radius(self):
        groups = [{"members": [{"x": x, "y": 0, "z": 0}]} for x in (0, 3, 40)]
        index = group_neighbor_index(groups)
        self.assertEqual(nearest_group((0, 0, 0), index), (3, 0, 0))
        self.assertIsNone(nearest_group((40, 0, 0), index))

    def test_dispersion_prefers_farther_valid_candidate(self):
        choices = [{"members": [{"x": x, "y": 0, "z": 0}]} for x in (-1, 1)]
        result = choose_step(choices, random.Random(1), (3, 0, 0), (0, 0, 0))
        self.assertEqual(result["members"][0]["x"], -1)

    def test_blocked_escape_keeps_random_legal_step(self):
        choices = [{"members": [{"x": 1, "y": 0, "z": 0}]}]
        self.assertIs(
            choose_step(choices, random.Random(1), (3, 0, 0), (0, 0, 0)), choices[0]
        )

    def test_no_players_no_planning(self):
        class NoRandom:
            def random(self):
                raise AssertionError("Empty maps must not spend random decisions")

        self.assertIsNone(
            plan_group_path(
                [{"id": -1, "x": 0, "y": 0, "z": 0}],
                [],
                (),
                neighbor_index={},
                rng=NoRandom(),
            )
        )

    def test_conditional_dispersion_uses_native_edges(self):
        from unittest.mock import patch

        members = [{"id": -1, "x": 0, "y": 0, "z": 0}]
        players = [{"x": 0, "y": 2, "z": 0}]
        edges = [((0, 0, 0), (x, 0, 0)) for x in (-1, 1)]
        with patch("wakfu_server.maps.monster_wander.random.random", return_value=0.1):
            result = plan_group_path(
                members,
                players,
                edges,
                min_steps=1,
                max_steps=1,
                neighbor_index={(0, 0): [(3, 0, 0)]},
            )
        self.assertEqual(result["members"][0]["x"], -1)

    def test_random_branch_does_not_query_neighbors(self):
        from unittest.mock import patch

        members = [{"id": -1, "x": 0, "y": 0, "z": 0}]
        with patch(
            "wakfu_server.maps.monster_wander.random.random", return_value=0.9
        ), patch(
            "wakfu_server.maps.monster_wander.nearest_group", side_effect=AssertionError
        ):
            result = plan_group_path(
                members,
                [{"x": 0, "y": 2, "z": 0}],
                [((0, 0, 0), (1, 0, 0))],
                min_steps=1,
                max_steps=1,
                neighbor_index={},
            )
        self.assertEqual(result["members"][0]["x"], 1)
