"""Pathfinding starts with visible available groups and rotates fairly."""
import unittest
from wakfu_server.monster_wander import visible_groups


class VisibleGroupsTests(unittest.TestCase):
    def test_far_population_does_not_spend_visible_budget_and_near_groups_rotate(self):
        far = [
            dict(group_id=i, status="available", members=[dict(x=10000 + i, y=0)])
            for i in range(5000)
        ]
        near = [
            dict(group_id=5000 + i, status="available", members=[dict(x=i, y=0)])
            for i in range(50)
        ]
        players = [dict(x=0, y=0), dict(x=49, y=0)]
        seen = set()
        for tick in range(7):
            selected = visible_groups(
                far + near, players, radius=25, tick=tick, batch_size=8
            )
            self.assertEqual(len(selected), 50)
            self.assertTrue(all(group["group_id"] >= 5000 for group in selected))
            seen.update(group["group_id"] for group in selected[:8])
        self.assertEqual(seen, set(range(5000, 5050)))

    def test_empty_players_fighting_and_exact_radius(self):
        groups = [
            dict(group_id=1, status="fighting", members=[dict(x=0, y=0)]),
            dict(group_id=2, status="available", members=[dict(x=10, y=-10)]),
            dict(group_id=3, status="available", members=[dict(x=11, y=0)]),
        ]
        self.assertEqual(
            visible_groups(groups, [], radius=10, tick=0, batch_size=8), []
        )
        self.assertEqual(
            [
                g["group_id"]
                for g in visible_groups(
                    groups, [dict(x=0, y=0)], radius=10, tick=0, batch_size=8
                )
            ],
            [2],
        )
