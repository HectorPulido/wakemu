import unittest
from unittest.mock import patch

from wakfu_server import monster_wander as wander


class FirstRng:
    def randint(self, low, high):
        return low

    def choice(self, choices):
        return choices[0]


class CohesiveTests(unittest.TestCase):
    def member(self, identity, x, y=0):
        return dict(id=identity, x=x, y=y, z=0)

    def test_compact_group_translates_with_one_search_and_keeps_offsets(self):
        members = [self.member(-1, 0), self.member(-2, 0, 1)]
        edges = [((0, 0, 0), (1, 0, 0)), ((0, 1, 0), (1, 1, 0))]
        with patch.object(wander, "plan_path", wraps=wander.plan_path) as search:
            result = wander.plan_group_path(
                members,
                [self.member(1, 10)],
                edges,
                rng=FirstRng(),
                min_steps=1,
                max_steps=1,
            )
        self.assertEqual(search.call_count, 1)
        self.assertEqual(
            [(m["x"], m["y"]) for m in result["members"]], [(1, 0), (1, 1)]
        )
        self.assertEqual(len(result["packets"]), 2)
        self.assertEqual(members[0]["x"], 0)

    def test_compact_group_cannot_split_when_one_edge_is_missing(self):
        result = wander.plan_group_path(
            [self.member(-1, 0), self.member(-2, 0, 1)],
            [self.member(1, 10)],
            [((0, 0, 0), (1, 0, 0))],
            rng=FirstRng(),
        )
        self.assertIsNone(result)

    def test_distant_follower_approaches_stationary_leader_by_native_edge(self):
        result = wander.plan_group_path(
            [self.member(-1, 0), self.member(-2, 8)],
            [self.member(1, 10)],
            [((8, 0, 0), (7, 0, 0))],
        )
        self.assertEqual([m["x"] for m in result["members"]], [0, 7])
        self.assertEqual(len(result["packets"]), 1)

    def test_regrouping_never_ignores_habitat_or_external_occupancy(self):
        members = [self.member(-1, 0), self.member(-2, 8)]
        for options in [
            dict(occupied={(7, 0, 0)}),
            dict(destination_allowed=lambda cell: False),
        ]:
            self.assertIsNone(
                wander.plan_group_path(
                    members, [self.member(1, 10)], [((8, 0, 0), (7, 0, 0))], **options
                )
            )

    def test_no_players_means_no_motion_even_for_scattered_group(self):
        self.assertIsNone(
            wander.plan_group_path(
                [self.member(-1, 0), self.member(-2, 8)], [], [((8, 0, 0), (7, 0, 0))]
            )
        )

    def test_regrouping_cannot_increase_distance_or_teleport(self):
        for edges in [[], [((8, 0, 0), (9, 0, 0))], [((8, 0, 0), (0, 0, 0))]]:
            self.assertIsNone(
                wander.plan_group_path(
                    [self.member(-1, 0), self.member(-2, 8)],
                    [self.member(1, 10)],
                    edges,
                )
            )


if __name__ == "__main__":
    unittest.main()
