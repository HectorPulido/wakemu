"""World validates fixed Rust-shaped overlap plans before publication.

Worker RNG/cadence and blocked path construction live in Rust mob_geometry's
actual overlap/wander admission kernels; these tests retain World guard checks.
"""

from test_ecology_mobs_apply import prepared_movement_packet
import unittest
from copy import deepcopy
from unittest.mock import patch

from protocol_codec import decode_body
from test_ecology_mobs_apply import FakeGroups, FakeHarvests, FakeWorld
from wakfu_server import (
    ecology_mobs,
    monster_wander,
)


class OverlapEscapeTests(unittest.TestCase):
    def apply_prepared_escape(self, overlap, *, blocked=False):
        """World half of the Rust overlap-recovery contract, using native frames."""
        configuration = dict(move_probability=0.0, radius=20, min_steps=1, max_steps=3)
        before = [dict(id=-701, ref=60, team=1, x=0, y=0, z=0)]
        if overlap == "own":
            before.append(dict(before[0], id=-702))
        rows = [dict(group_id=701, status="available", members=before)]
        if overlap == "other":
            rows.append(
                dict(
                    group_id=703, status="fighting", members=[dict(before[0], id=-703)]
                )
            )
        players = [
            dict(
                id=40,
                map_id=999999,
                instance_id=0,
                x=0,
                y=0 if overlap == "player" else 3,
                z=0,
            )
        ]
        # Fixed prepared result, not a Python path search. Rust's overlap tests
        # certify construction; World still owns terrain/occupancy/CAS checks.
        moved = [
            dict(member, x=1 if index == 0 else -1)
            for index, member in enumerate(before)
        ]
        packets = [
            [opcode, payload.hex()]
            for opcode, payload in (
                prepared_movement_packet(old["id"], (0, 0, 0), (new["x"], 0, 0))
                for old, new in zip(before, moved)
            )
        ]
        proposal = dict(
            kind="wander_bulk",
            world_epoch="overlap",
            scope=[999999, 0],
            configuration=configuration,
            moves=[
                dict(
                    group_id=701,
                    expected_members=deepcopy(before),
                    moved_members=moved,
                    packets=packets,
                    overlap_escape=True,
                )
            ],
        )
        groups = FakeGroups(deepcopy(rows))
        world = FakeWorld(players)
        edges = [] if blocked else [((0, 0, 0), (1, 0, 0)), ((0, 0, 0), (-1, 0, 0))]
        with patch.object(
            monster_wander, "policy", return_value=configuration
        ), patch.object(
            ecology_mobs, "_edges", return_value=monster_wander.edge_index(edges)
        ):
            result = ecology_mobs.apply(
                object(), groups, FakeHarvests(), world, proposal, world_epoch="overlap"
            )
        if blocked:
            self.assertEqual(result["status"], "stale_group")
            self.assertEqual(groups.move_calls, [])
            self.assertEqual(world.emitted, [])
            return proposal, groups, world
        self.assertEqual(result.get("applied_groups"), 1)
        endpoints = [monster_wander.point(member) for member in moved]
        self.assertEqual(len(set(endpoints)), len(endpoints))
        self.assertTrue(all(cell != (0, 0, 0) for cell in endpoints))
        decoded = [
            decode_body("in", opcode, body) for opcode, body in world.emitted[0][2]
        ]
        self.assertEqual(
            {p["actor_id"] for p in decoded}, {member["id"] for member in before}
        )
        return proposal, groups, world

    def test_prepared_player_other_and_own_escape_is_accepted_at_zero_probability(self):
        for overlap in ("player", "other", "own"):
            with self.subTest(overlap=overlap):
                self.apply_prepared_escape(overlap)

    def test_prepared_player_escape_needs_no_nearby_monster(self):
        proposal, _, _ = self.apply_prepared_escape("player")
        self.assertTrue(proposal["moves"][0]["overlap_escape"])

    def test_prepared_escape_cannot_cross_missing_native_edges(self):
        for overlap in ("player", "other", "own"):
            with self.subTest(overlap=overlap):
                self.apply_prepared_escape(overlap, blocked=True)

    def test_recovery_marker_cannot_fake_overlap_keep_it_unchanged_or_skip_terrain(
        self,
    ):
        before = dict(id=-701, ref=60, team=1, x=0, y=0, z=0)
        after = dict(before, x=1)
        opcode, body = prepared_movement_packet(-701, (0, 0, 0), (1, 0, 0))
        configuration = dict(move_probability=0.0, radius=20, min_steps=1, max_steps=3)
        proposal = dict(
            kind="wander_bulk",
            world_epoch="overlap",
            scope=[999999, 0],
            configuration=configuration,
            moves=[
                dict(
                    group_id=701,
                    expected_members=[before],
                    moved_members=[after],
                    packets=[[opcode, body.hex()]],
                    overlap_escape=True,
                )
            ],
        )
        for source_overlap, occupied_endpoint, native_edge in (
            (False, False, True),
            (True, True, True),
            (True, False, False),
        ):
            with self.subTest(
                source_overlap=source_overlap,
                occupied_endpoint=occupied_endpoint,
                native_edge=native_edge,
            ):
                players = [
                    dict(
                        id=40,
                        map_id=999999,
                        instance_id=0,
                        x=0,
                        y=0 if source_overlap else 3,
                        z=0,
                    )
                ]
                if occupied_endpoint:
                    players.append(dict(players[0], id=41, x=1, y=0))
                groups = FakeGroups(
                    [dict(group_id=701, status="available", members=[before])]
                )
                world = FakeWorld(players)
                indexed = monster_wander.edge_index(
                    [((0, 0, 0), (1, 0, 0))] if native_edge else []
                )
                with patch.object(
                    monster_wander, "policy", return_value=configuration
                ), patch.object(ecology_mobs, "_edges", return_value=indexed):
                    result = ecology_mobs.apply(
                        object(),
                        groups,
                        FakeHarvests(),
                        world,
                        proposal,
                        world_epoch="overlap",
                    )
                self.assertEqual(result["status"], "stale_group")
                self.assertEqual(groups.move_calls, [])
                self.assertEqual(world.emitted, [])
