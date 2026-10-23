"""Only verified separation may ignore actors, while native terrain remains binding."""
import unittest
import struct
import random
from copy import deepcopy
from unittest.mock import patch
from protocol_codec import decode_body

from test_ecology_mobs_apply import FakeGroups, FakeHarvests, FakeWorld
from wakfu_server import ecology_mobs, monster_wander


class FleeingMovementApplyTests(unittest.TestCase):
    configuration = dict(move_probability=1.0, radius=20, min_steps=1, max_steps=3)

    def test_seeded_escape_mixes_branches_and_routes_with_outward_drift(self):
        for origin in ((1, 0, 0), (0, 1, 0), (-1, 0, 0)):
            with self.subTest(origin=origin):
                x, y, z = origin
                destinations = [
                    (x + dx, y + dy, z)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if (x + dx) ** 2 + (y + dy) ** 2 > x * x + y * y
                ]
                members = [dict(id=-701, x=x, y=y, z=z)]
                threat = [
                    dict(status="available", members=[dict(id=-703, x=0, y=0, z=0)])
                ]
                routes = set()
                distances = []
                for seed in range(100):
                    plan = monster_wander.plan_group_path(
                        members,
                        [dict(x=x, y=y + 3, z=0)],
                        [(origin, cell) for cell in destinations]
                        + [
                            (cell, tuple(2 * b - a for a, b in zip(origin, cell)))
                            for cell in destinations
                        ],
                        occupied=destinations,
                        other_groups=threat,
                        rng=random.Random(seed),
                        min_steps=2,
                        max_steps=2,
                    )
                    if plan is None:
                        continue
                    self.assertTrue(plan["dispersal"])
                    cell = monster_wander.point(plan["members"][0])
                    routes.add(cell)
                    distances.append(cell[0] ** 2 + cell[1] ** 2)
                self.assertGreater(len(routes), 1)
                self.assertGreater(len(distances), 0)
                self.assertLess(len(distances), 100)
                self.assertGreater(sum(distances) / len(distances), x * x + y * y)

    def test_planner_ignores_all_actor_occupancy_only_on_its_escape_branch(self):
        class Rng:
            def __init__(self, roll):
                self.roll = roll

            def random(self):
                return self.roll

            def randint(self, low, high):
                return low

            def choice(self, values):
                return values[0]

        members = [dict(id=-701, x=1, y=0, z=0), dict(id=-702, x=3, y=0, z=0)]
        players = [dict(id=40, x=2, y=0, z=0)]
        others = [
            dict(status="available", members=[dict(id=-703, x=0, y=0, z=0)]),
            dict(status="available", members=[dict(id=-704, x=2, y=0, z=0)]),
        ]
        edges = [((1, 0, 0), (0, 0, 0))] + [
            ((x, 0, 0), (x + 1, 0, 0)) for x in range(1, 5)
        ]
        for roll, allowed, expected in (
            (0.0, True, True),
            (0.9, True, False),
            (0.0, False, False),
        ):
            with self.subTest(roll=roll, surface_allowed=allowed):
                plan = monster_wander.plan_group_path(
                    members,
                    players,
                    edges,
                    occupied=[(0, 0, 0), (2, 0, 0)],
                    other_groups=others,
                    rng=Rng(roll),
                    min_steps=3,
                    max_steps=3,
                    destination_allowed=lambda _cell: allowed,
                )
                if not allowed:
                    self.assertIsNone(plan)
                    continue
                if not expected:
                    self.assertFalse(plan and plan.get("dispersal", False))
                    continue
                self.assertTrue(plan["dispersal"])
                self.assertTrue(
                    monster_wander.clear_destination(plan["members"], players, others)
                )
                self.assertTrue(
                    monster_wander.separating_movement(members, plan["members"], others)
                )

    def apply_movement(
        self,
        *,
        dispersal=True,
        destination=4,
        native_edge=True,
        surface=True,
        include_threat=True,
        path=None
    ):
        def member(actor_id, x):
            return dict(id=actor_id, ref=60, team=1, x=x, y=0, z=0)

        before = [member(-701, 1), member(-702, 2)]
        path = (
            [(x, 0, 0) for x in range(1, destination + 1)]
            if path is None and destination > 1
            else ([(1, 0, 0), (destination, 0, 0)] if path is None else path)
        )
        moved = [
            dict(before[0], x=path[-1][0], y=path[-1][1], z=path[-1][2]),
            dict(before[1], x=path[-1][0] + 1, y=path[-1][1], z=path[-1][2]),
        ]
        deltas = bytes(
            monster_wander.movement_packet(-701, a, b)[1][-1]
            for a, b in zip(path, path[1:])
        )
        opcode, body = (
            13852,
            struct.pack(">qiihB", -701, *path[0], len(deltas)) + deltas,
        )
        follower_path = [(cell[0] + 1, cell[1], cell[2]) for cell in path]
        follower_deltas = bytes(
            monster_wander.movement_packet(-702, a, b)[1][-1]
            for a, b in zip(follower_path, follower_path[1:])
        )
        follower_body = (
            struct.pack(">qiihB", -702, *follower_path[0], len(follower_deltas))
            + follower_deltas
        )
        move = dict(
            group_id=701,
            expected_members=before,
            moved_members=moved,
            packets=[[opcode, body.hex()], [opcode, follower_body.hex()]],
        )
        if dispersal is not None:
            move["dispersal"] = dispersal
        proposal = dict(
            kind="wander_bulk",
            world_epoch="flee",
            scope=[999999, 0],
            configuration=self.configuration,
            moves=[move],
        )
        rows = [dict(group_id=701, status="available", members=before)]
        if include_threat:
            rows.append(
                dict(group_id=703, status="available", members=[member(-703, 0)])
            )
        # A different group's actor and our own companion share the destination.
        rows.append(dict(group_id=704, status="available", members=[member(-704, 2)]))
        groups = FakeGroups(rows)
        world = FakeWorld([dict(id=40, map_id=999999, instance_id=0, x=2, y=0, z=0)])
        indexed = monster_wander.edge_index(
            list(zip(path, path[1:])) + list(zip(follower_path, follower_path[1:]))
            if native_edge
            else []
        )
        with patch.object(
            monster_wander, "policy", return_value=self.configuration
        ), patch.object(ecology_mobs, "_edges", return_value=indexed), patch.object(
            ecology_mobs.time, "monotonic", return_value=0
        ), patch.object(
            ecology_mobs, "habitat_destination_allowed", return_value=surface
        ):
            result = ecology_mobs.apply(
                object(), groups, FakeHarvests(), world, proposal, world_epoch="flee"
            )
        return result, groups, world

    def test_verified_flight_can_cross_actors_but_ends_on_clear_cells(self):
        result, groups, world = self.apply_movement()
        self.assertEqual(result.get("applied_groups"), 1)
        self.assertEqual(len(groups.move_calls), 1)
        self.assertEqual(len(world.emitted), 1)

    def test_ordinary_movement_preserves_actor_collision(self):
        result, groups, world = self.apply_movement(dispersal=None)
        self.assertEqual(result["status"], "stale_group")
        self.assertEqual(groups.move_calls, [])
        self.assertEqual(world.emitted, [])

    def test_dispersal_cannot_finish_on_an_occupied_endpoint(self):
        result, groups, world = self.apply_movement(destination=2)
        self.assertEqual(result["status"], "stale_group")
        self.assertEqual(groups.move_calls, [])
        self.assertEqual(world.emitted, [])

    def test_flight_marker_cannot_bypass_native_edges_or_surfaces(self):
        for overrides in (dict(native_edge=False), dict(surface=False)):
            with self.subTest(overrides=overrides):
                result, groups, world = self.apply_movement(**overrides)
                self.assertEqual(result["status"], "stale_group")
                self.assertEqual(groups.move_calls, [])
                self.assertEqual(world.emitted, [])

    def test_flight_marker_cannot_authorize_a_step_toward_the_actual_threat(self):
        result, groups, world = self.apply_movement(destination=0)
        self.assertEqual(result["status"], "stale_group")
        self.assertEqual(groups.move_calls, [])
        self.assertEqual(world.emitted, [])

    def test_farther_endpoint_cannot_hide_an_intermediate_step_toward_the_threat(self):
        result, groups, world = self.apply_movement(
            path=[(1, 0, 0), (0, 0, 0), (1, 1, 0), (2, 1, 0)]
        )
        self.assertEqual(result["status"], "stale_group")
        self.assertEqual(groups.move_calls, [])
        self.assertEqual(world.emitted, [])

    def test_false_or_malformed_flight_marker_cannot_bypass_collision(self):
        for flag in (False, 1, "true"):
            with self.subTest(flag=flag):
                result, groups, world = self.apply_movement(dispersal=flag)
                self.assertEqual(result["status"], "stale_group")
                self.assertEqual(groups.move_calls, [])
                self.assertEqual(world.emitted, [])

    def test_recalculated_nearest_threat_prevents_stale_flight_permission(self):
        result, groups, world = self.apply_movement(include_threat=False)
        self.assertEqual(result["status"], "stale_group")
        self.assertEqual(groups.move_calls, [])
        self.assertEqual(world.emitted, [])
