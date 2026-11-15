"""Only verified separation may ignore actors, while native terrain remains binding."""

import unittest
import struct
from unittest.mock import patch

from test_ecology_mobs_apply import (
    FakeGroups,
    FakeHarvests,
    FakeWorld,
    prepared_movement_packet,
)
from wakfu_server import ecology_mobs, monster_wander


class FleeingMovementApplyTests(unittest.TestCase):
    configuration = dict(move_probability=1.0, radius=20, min_steps=1, max_steps=3)

    # Actual native planner assertions moved to legacy_wander_contract:
    # seeded_dispersal_keeps_native_routes_varied_and_outward and
    # dispersal_can_cross_actors_but_still_requires_habitat_and_clear_endpoints.

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
            prepared_movement_packet(-701, a, b)[1][-1] for a, b in zip(path, path[1:])
        )
        opcode, body = (
            13852,
            struct.pack(">qiihB", -701, *path[0], len(deltas)) + deltas,
        )
        follower_path = [(cell[0] + 1, cell[1], cell[2]) for cell in path]
        follower_deltas = bytes(
            prepared_movement_packet(-702, a, b)[1][-1]
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
            ecology_mobs, "_native_habitat_paths_allowed", return_value=surface
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
