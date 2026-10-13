"""Crowded formation regressions without a database or native catalog fixture."""
import unittest
from wakfu_server.monster_wander import edge_index, plan_group_path, point


class FixedRng:
    def randint(self, low, high):
        return low

    def choice(self, values):
        return values[0]

    def random(self):
        raise AssertionError("The planner must not add actor probability draws")


class CrowdedFormationTests(unittest.TestCase):
    def setUp(self):
        self.members = [dict(id=-1, x=-57, y=8, z=0), dict(id=-2, x=-59, y=11, z=0)]
        self.players = [dict(x=-63, y=8, z=0)]
        self.edges = [
            ((-57, 8, 0), (-57, 9, 0)),
            ((-57, 8, 0), (-56, 8, 0)),
            ((-57, 8, 0), (-58, 8, 0)),
            ((-57, 8, 0), (-57, 7, 0)),
            ((-59, 11, 0), (-60, 11, 0)),
            ((-59, 11, 0), (-59, 10, 0)),
            ((-59, 11, 0), (-58, 11, 0)),
        ]
        self.blocked = [(-56, 8, 0), (-58, 8, 0), (-57, 7, 0)]

    def run_plan(self, **kwargs):
        options = dict(
            indexed=edge_index(self.edges),
            occupied=self.blocked,
            min_steps=1,
            max_steps=1,
            rng=FixedRng(),
        )
        options.update(kwargs)
        return plan_group_path(self.members, self.players, (), **options)

    def test_runtime_gobballs_can_move_when_companion_holds(self):
        result = self.run_plan()
        self.assertEqual(
            [point(m) for m in result["members"]], [(-57, 9, 0), (-59, 11, 0)]
        )
        self.assertEqual(len(result["packets"]), 1)
        self.assertEqual(point(self.members[0]), (-57, 8, 0))

    def test_crowded_miaumiau_and_mixed_groups_use_the_same_planner(self):
        for references in ((2616, 2617), (2598, 2616), (39, 2616)):
            with self.subTest(references=references):
                for member, reference in zip(self.members, references):
                    member["ref"] = reference
                result = self.run_plan()
                self.assertEqual(
                    [point(m) for m in result["members"]], [(-57, 9, 0), (-59, 11, 0)]
                )
                self.assertEqual(
                    [m["ref"] for m in result["members"]], list(references)
                )
                self.assertEqual(len(result["packets"]), 1)

    def test_empty_map_remains_stationary(self):
        self.players = []
        self.assertIsNone(self.run_plan())

    def test_zero_radius_remains_stationary(self):
        self.players = [dict(x=-57, y=8, z=0)]
        self.assertIsNone(self.run_plan(radius=0))

    def test_habitat_rejection_cannot_be_bypassed(self):
        self.assertIsNone(
            self.run_plan(destination_allowed=lambda cell: cell != (-57, 9, 0))
        )

    def test_fallback_cannot_walk_through_held_companion(self):
        self.members = [dict(id=-1, x=0, y=0, z=0), dict(id=-2, x=1, y=0, z=0)]
        self.players = [dict(x=0, y=2, z=0)]
        self.edges = [((0, 0, 0), (1, 0, 0))]
        self.blocked = []
        self.assertIsNone(self.run_plan())

    def test_fallback_cannot_exceed_cohesion_radius(self):
        self.members = [dict(id=-1, x=0, y=0, z=0), dict(id=-2, x=-4, y=0, z=0)]
        self.players = [dict(x=0, y=2, z=0)]
        self.edges = [((0, 0, 0), (1, 0, 0))]
        self.blocked = []
        self.assertIsNone(self.run_plan())
