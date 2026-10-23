"""Existing actor overlap must clear promptly through native cells and free endpoints."""
import unittest
from contextlib import ExitStack
from copy import deepcopy
from unittest.mock import MagicMock, patch

from protocol_codec import decode_body
from test_ecology_mobs_apply import FakeGroups, FakeHarvests, FakeWorld
from wakfu_server import (
    ecology_mobs,
    monster_maturation,
    monster_reproduction,
    monster_wander,
)


class OverlapEscapeTests(unittest.TestCase):
    def prepare_and_apply(self, overlap, *, blocked=False, allow_wander=True):
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
        snapshot = dict(
            world_epoch="overlap",
            excluded_ids=[],
            locations=[[999999, 0]],
            now_ms=1000,
            players=players,
            allow_wander=allow_wander,
        )
        store = MagicMock()
        db = store.connection.return_value.__enter__.return_value
        db.execute.side_effect = (
            lambda sql, *_: rows if "FROM combat_groups" in sql else []
        )
        edges = [] if blocked else [((0, 0, 0), (1, 0, 0)), ((0, 0, 0), (-1, 0, 0))]
        with ExitStack() as patches:
            for domain in (monster_maturation, monster_reproduction):
                patches.enter_context(patch.object(domain, "policy", return_value={}))
                patches.enter_context(patch.object(domain, "observe"))
                patches.enter_context(patch.object(domain, "pending", return_value=[]))
                patches.enter_context(
                    patch.object(domain, "unpublished", return_value=[])
                )
            patches.enter_context(
                patch(
                    "wakfu_server.monster_population_cleanup.prepare", return_value=[]
                )
            )
            patches.enter_context(
                patch.object(
                    monster_reproduction, "dungeon_population", return_value=False
                )
            )
            patches.enter_context(
                patch.object(monster_wander, "policy", return_value=configuration)
            )
            patches.enter_context(
                patch.object(
                    ecology_mobs,
                    "_edges",
                    return_value=monster_wander.edge_index(edges),
                )
            )
            patches.enter_context(
                patch.object(ecology_mobs.random, "random", return_value=0.99)
            )
            patches.enter_context(
                patch.object(ecology_mobs.time, "monotonic", return_value=0)
            )
            plans = ecology_mobs.prepare(store, snapshot, limit=1)
            if blocked:
                return plans, None, None
            self.assertEqual(len(plans), 1)
            move = next(move for move in plans[0]["moves"] if move["group_id"] == 701)
            self.assertTrue(move["overlap_escape"])
            endpoints = [monster_wander.point(m) for m in move["moved_members"]]
            self.assertEqual(len(set(endpoints)), len(endpoints))
            if overlap != "own":
                self.assertTrue(all(cell != (0, 0, 0) for cell in endpoints))
            groups = FakeGroups(deepcopy(rows))
            world = FakeWorld(players)
            result = ecology_mobs.apply(
                store, groups, FakeHarvests(), world, plans[0], world_epoch="overlap"
            )
            self.assertEqual(result.get("applied_groups"), 1)
            decoded = [decode_body("in", op, body) for op, body in world.emitted[0][2]]
            changed_ids = {
                old["id"]
                for old, new in zip(before, move["moved_members"])
                if monster_wander.point(old) != monster_wander.point(new)
            }
            self.assertEqual({p["actor_id"] for p in decoded}, changed_ids)
            return plans, groups, world

    def test_player_other_and_own_overlap_move_even_when_probability_and_rng_skip(self):
        for overlap in ("player", "other", "own"):
            with self.subTest(overlap=overlap):
                self.prepare_and_apply(overlap)

    def test_player_only_overlap_does_not_require_a_nearby_monster(self):
        plans, _, _ = self.prepare_and_apply("player")
        self.assertTrue(plans[0]["moves"][0]["overlap_escape"])

    def test_overlap_recovery_runs_even_outside_the_random_wander_cadence(self):
        for overlap in ("player", "other", "own"):
            with self.subTest(overlap=overlap):
                self.prepare_and_apply(overlap, allow_wander=False)

    def test_blocked_native_geometry_waits_without_teleporting(self):
        for overlap in ("player", "other", "own"):
            with self.subTest(overlap=overlap):
                plans, _, _ = self.prepare_and_apply(overlap, blocked=True)
                self.assertEqual(plans, [])

    def test_recovery_marker_cannot_fake_overlap_keep_it_unchanged_or_skip_terrain(
        self,
    ):
        before = dict(id=-701, ref=60, team=1, x=0, y=0, z=0)
        after = dict(before, x=1)
        opcode, body = monster_wander.movement_packet(-701, (0, 0, 0), (1, 0, 0))
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
