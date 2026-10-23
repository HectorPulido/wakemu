"""Blocked anchors may hold while companions move through durable publication."""
from unittest.mock import patch
import random

from postgres_case import PostgresCase
from protocol_codec import decode_body
from test_ecology_mobs_apply import FakeHarvests, FakeWorld
from test_monster_wander_crowded import FixedRng
from wakfu_server import ecology_mobs, monster_wander
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import owned_instance


class BlockedAnchorPublicationTests(PostgresCase):
    def test_overlap_recovery_persists_distinct_free_endpoints_and_publishes(self):
        scope = (999999, 0)
        groups = PersistentGroups(self.store)

        def member(actor_id, x):
            return owned_instance(4, 10, actor_id, map_id=scope[0], x=x, y=0, z=0)

        members = [member(-7201, 1), member(-7202, 1)]
        groups.register(*scope, 7201, members)
        groups.register(*scope, 7203, [member(-7203, 0)])
        groups.register(*scope, 7204, [member(-7204, 1)])
        players = [dict(id=40, map_id=scope[0], instance_id=0, x=1, y=0, z=0)]
        configuration = dict(move_probability=1.0, radius=20, min_steps=1, max_steps=3)
        edges = [((1, 0, 0), (2, 0, 0)), ((2, 0, 0), (3, 0, 0))]
        planned = monster_wander.plan_group_path(
            members,
            players,
            edges,
            occupied=[(0, 0, 0), (1, 0, 0)],
            other_groups=groups.snapshot(*scope),
            rng=random.Random(1),
            min_steps=1,
            max_steps=3,
        )
        self.assertTrue(planned["overlap_escape"])
        proposal = dict(
            kind="wander_bulk",
            world_epoch="overlap",
            scope=list(scope),
            configuration=configuration,
            moves=[
                dict(
                    group_id=7201,
                    expected_members=members,
                    moved_members=planned["members"],
                    overlap_escape=True,
                    packets=[[op, body.hex()] for op, body in planned["packets"]],
                )
            ],
        )
        world = FakeWorld(players)
        with patch.object(
            monster_wander, "policy", return_value=configuration
        ), patch.object(
            ecology_mobs, "_edges", return_value=monster_wander.edge_index(edges)
        ):
            applied = ecology_mobs.apply(
                self.store,
                groups,
                FakeHarvests(),
                world,
                proposal,
                world_epoch="overlap",
            )
        self.assertEqual(applied["applied_groups"], 1)
        durable = next(row for row in groups.snapshot(*scope) if row["key"][2] == 7201)
        endpoints = [monster_wander.point(m) for m in durable["members"]]
        self.assertEqual(set(endpoints), {(2, 0, 0), (3, 0, 0)})
        self.assertEqual(len(world.emitted[0][2]), 2)
        decoded = [decode_body("in", *packet) for packet in world.emitted[0][2]]
        self.assertEqual({p["actor_id"] for p in decoded}, {m["id"] for m in members})
        self.assertEqual(
            {tuple(p["end_position"][k] for k in ("x", "y", "z")) for p in decoded},
            set(endpoints),
        )

    def test_companion_move_commits_and_publishes_with_stationary_blocked_anchor(self):
        scope = (999999, 0)
        groups = PersistentGroups(self.store)

        def member(actor_id, x, y):
            return owned_instance(4, 10, actor_id, map_id=scope[0], x=x, y=y, z=0)

        members = [member(-7101, 0, 0), member(-7102, 0, 1)]
        blocker = member(-7103, 1, 0)
        groups.register(*scope, 7101, members)
        groups.register(*scope, 7103, [blocker])
        players = [dict(id=40, map_id=scope[0], instance_id=0, x=0, y=3, z=0)]
        configuration = dict(move_probability=1.0, radius=20, min_steps=1, max_steps=1)
        planned = monster_wander.plan_group_path(
            members,
            players,
            [((0, 0, 0), (1, 0, 0)), ((0, 1, 0), (1, 1, 0))],
            occupied=[monster_wander.point(blocker)],
            rng=FixedRng(),
            min_steps=1,
            max_steps=1,
        )
        self.assertIsNotNone(planned)
        self.assertEqual(planned["members"][0], members[0])
        self.assertEqual(monster_wander.point(planned["members"][1]), (1, 1, 0))
        proposal = dict(
            kind="wander_bulk",
            world_epoch="blocked-anchor",
            scope=list(scope),
            configuration=configuration,
            moves=[
                dict(
                    group_id=7101,
                    expected_members=members,
                    moved_members=planned["members"],
                    packets=[[op, body.hex()] for op, body in planned["packets"]],
                )
            ],
        )
        world = FakeWorld(players)
        with patch.object(monster_wander, "policy", return_value=configuration):
            applied = ecology_mobs.apply(
                self.store,
                groups,
                FakeHarvests(),
                world,
                proposal,
                world_epoch="blocked-anchor",
            )
            replay = ecology_mobs.apply(
                self.store,
                groups,
                FakeHarvests(),
                world,
                proposal,
                world_epoch="blocked-anchor",
            )
        self.assertEqual(applied["applied_groups"], 1)
        self.assertEqual(replay["status"], "stale_group")
        durable = next(row for row in groups.snapshot(*scope) if row["key"][2] == 7101)
        self.assertEqual(list(durable["members"]), planned["members"])
        self.assertEqual(len(world.emitted), 1)
        self.assertEqual(len(world.emitted[0][2]), 1)
        opcode, payload = world.emitted[0][2][0]
        decoded = decode_body("in", opcode, payload)
        self.assertEqual(decoded["actor_id"], members[1]["id"])
        self.assertEqual(decoded["start_position"], dict(x=0, y=1, z=0))
        self.assertEqual(decoded["end_position"], dict(x=1, y=1, z=0))
