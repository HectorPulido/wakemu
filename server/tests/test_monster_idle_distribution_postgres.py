"""Durable empty-map plans change positions once and cancel on reoccupation."""
from copy import deepcopy
from unittest.mock import patch
import threading

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import monster_idle_distribution_store as idle
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance
from test_monster_idle_distribution import grid
from test_ecology_mobs_apply import FakeHarvests
from wakfu_server import ecology_mobs
from wakfu_server.world import World


class IdleDistributionPostgresTests(PostgresCase):
    def test_independent_chunks_commit_in_reverse_order_once_without_changing_owned_data(
        self,
    ):
        scope = (999999, 0)
        groups = PersistentGroups(self.store)
        moves = []
        for index in range(9):
            member = owned_instance(
                4,
                REFERENCES[4]["min_level"],
                -9000 - index,
                map_id=scope[0],
                x=index,
                y=0,
                z=0,
            )
            groups.register(*scope, 9000 + index, [member])
            moves.append(
                dict(
                    group_id=9000 + index,
                    expected_members=[member],
                    moved_members=[dict(member, x=index + 10, y=10)],
                )
            )
        idle.freeze(self.store, epoch="reverse", scope=scope, generation=1, moves=moves)
        proposals = idle.pending(
            self.store, epoch="reverse", scope=scope, generation=1, limit=16
        )
        self.assertEqual([p["chunk_index"] for p in proposals], [0, 1])
        self.assertEqual(
            [len(idle.read_chunk(self.store, p)) for p in proposals], [8, 1]
        )
        with patch("wakfu_server.combat_terrain.map_geometry", return_value=grid(32)):
            prepared = [idle.validate_chunk(self.store, p) for p in proposals]
        for proposal, chunk in reversed(list(zip(proposals, prepared))):
            outcomes = idle.commit(
                self.store, groups, proposal, episode_current=True, prepared=chunk
            )
            self.assertTrue(outcomes)
            self.assertTrue(all(row["status"] == "applied" for row in outcomes))
            self.assertEqual(
                idle.commit(
                    self.store, groups, proposal, episode_current=True, prepared=chunk
                ),
                [],
            )
        self.assertEqual(
            idle.pending(
                self.store, epoch="reverse", scope=scope, generation=1, limit=16
            ),
            [],
        )
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT group_id,members,revision FROM combat_groups "
                "WHERE map_id=%s AND instance_id=%s ORDER BY group_id",
                scope,
            ).fetchall()
            membership = db.execute(
                "SELECT monster_id,group_id FROM combat_group_members "
                "WHERE map_id=%s AND instance_id=%s",
                scope,
            ).fetchall()
        self.assertEqual(len(rows), 9)
        self.assertEqual(
            {(row["monster_id"], row["group_id"]) for row in membership},
            {(move["expected_members"][0]["id"], move["group_id"]) for move in moves},
        )
        for row, move in zip(rows, moves):
            self.assertEqual(row["members"], move["moved_members"])
            self.assertEqual(row["revision"], 1)
            self.assertEqual(
                {
                    k: v
                    for k, v in row["members"][0].items()
                    if k not in ("x", "y", "z")
                },
                {
                    k: v
                    for k, v in move["expected_members"][0].items()
                    if k not in ("x", "y", "z")
                },
            )

    def test_world_apply_cancels_a_join_race_and_applies_the_next_empty_episode_once(
        self,
    ):
        scope = (999999, 0)
        groups = PersistentGroups(self.store)
        member = owned_instance(
            4, REFERENCES[4]["min_level"], -8300, map_id=scope[0], x=0, y=0, z=0
        )
        groups.register(*scope, 8300, [member])
        world = World(lambda _: b"", lambda _: b"", lambda *_: None)
        player = dict(id=1, account_id=1, map_id=scope[0], instance_id=0, x=0, y=0, z=0)
        world.join("first", object(), player)
        world.leave(1, "first")
        generation = world.empty_scope_generation(*scope)
        moved = [dict(member, x=10, y=10)]
        moves = [dict(group_id=8300, expected_members=[member], moved_members=moved)]
        idle.freeze(
            self.store, epoch="race", scope=scope, generation=generation, moves=moves
        )
        proposal = idle.pending(
            self.store, epoch="race", scope=scope, generation=generation
        )[0]
        prepared = threading.Event()
        continue_commit = threading.Event()
        outcomes, errors = [], []
        original_validate = idle.validate_chunk

        def pause_after_validation(store, proposal):
            result = original_validate(store, proposal)
            prepared.set()
            if not continue_commit.wait(3):
                raise AssertionError(
                    "Join race did not release prepared idle distribution"
                )
            return result

        def apply():
            try:
                outcomes.append(
                    ecology_mobs.apply(
                        self.store,
                        groups,
                        FakeHarvests(),
                        world,
                        proposal,
                        world_epoch="race",
                    )
                )
            except BaseException as error:
                errors.append(error)

        with patch(
            "wakfu_server.combat_terrain.map_geometry", return_value=grid(32)
        ), patch.object(idle, "validate_chunk", side_effect=pause_after_validation):
            worker = threading.Thread(target=apply, daemon=True)
            worker.start()
            try:
                self.assertTrue(prepared.wait(3))
                world.join("returned", object(), player)
            finally:
                continue_commit.set()
                worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(outcomes[0]["status"], "stale")
        with self.store.connection() as db:
            row = db.execute(
                "SELECT members,revision FROM combat_groups WHERE map_id=%s "
                "AND instance_id=%s AND group_id=8300",
                scope,
            ).fetchone()
        self.assertEqual(row["members"], [member])
        self.assertEqual(row["revision"], 0)

        world.leave(1, "returned")
        next_generation = world.empty_scope_generation(*scope)
        self.assertNotEqual(generation, next_generation)
        idle.freeze(
            self.store,
            epoch="race",
            scope=scope,
            generation=next_generation,
            moves=moves,
        )
        proposal = idle.pending(
            self.store, epoch="race", scope=scope, generation=next_generation
        )[0]
        with patch("wakfu_server.combat_terrain.map_geometry", return_value=grid(32)):
            applied = ecology_mobs.apply(
                self.store, groups, FakeHarvests(), world, proposal, world_epoch="race"
            )
            replay = ecology_mobs.apply(
                self.store, groups, FakeHarvests(), world, proposal, world_epoch="race"
            )
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["applied_groups"], 1)
        self.assertEqual(replay["status"], "duplicate")
        with self.store.connection() as db:
            row = db.execute(
                "SELECT members,revision FROM combat_groups WHERE map_id=%s "
                "AND instance_id=%s AND group_id=8300",
                scope,
            ).fetchone()
        self.assertEqual(row["members"], moved)
        self.assertEqual(row["revision"], 1)

    def test_frozen_episode_cas_preserves_owned_rosters_and_cancels_after_reentry(self):
        scope = (999999, 0)
        groups = PersistentGroups(self.store)
        members = [
            owned_instance(
                4,
                REFERENCES[4]["min_level"],
                -8100 - index,
                map_id=scope[0],
                x=index,
                y=0,
                z=0,
            )
            for index in range(8)
        ]
        second = [
            owned_instance(
                4, REFERENCES[4]["min_level"], -8200, map_id=scope[0], x=-10, y=0, z=0
            )
        ]
        groups.register(*scope, 8100, members)
        groups.register(*scope, 8200, second)
        # Existing durable health is independent of a newly constructed native
        # actor's full-health descriptor. Distribution must retain this state.
        for index, member in enumerate(members):
            member["hp"] = max(1, member["max_hp"] - index - 1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET members=%s WHERE map_id=%s "
                "AND instance_id=%s AND group_id=8100",
                (Jsonb(members), *scope),
            )
        moved = [
            dict(member, x=30 + index, y=10) for index, member in enumerate(members)
        ]
        moves = [
            dict(group_id=8100, expected_members=members, moved_members=moved),
            dict(
                group_id=8200,
                expected_members=second,
                moved_members=[dict(second[0], x=40, y=10)],
            ),
        ]
        run = idle.freeze(
            self.store, epoch="idle-test", scope=scope, generation=1, moves=moves
        )
        different = deepcopy(moves)
        different[0]["moved_members"][0]["x"] = 100
        self.assertEqual(
            idle.freeze(
                self.store,
                epoch="idle-test",
                scope=scope,
                generation=1,
                moves=different,
            ),
            run,
        )
        proposal = idle.pending(
            self.store, epoch="idle-test", scope=scope, generation=1
        )[0]
        self.assertEqual(
            idle.read_chunk(self.store, proposal)[0]["moved_members"], moved
        )
        snapshot = dict(
            world_epoch="idle-test",
            players=[],
            locations=[],
            excluded_ids=[],
            now_ms=1000,
            empty_scopes=[
                dict(map_id=scope[0], instance_id=scope[1], empty_generation=1)
            ],
        )
        with patch(
            "wakfu_server.monster_idle_distribution.plan",
            side_effect=AssertionError("Frozen empty episode was planned twice"),
        ):
            self.assertEqual(
                ecology_mobs.prepare(self.store, snapshot, limit=1), [proposal]
            )

        stale = [dict(second[0], x=-11)]
        self.assertTrue(groups.move_members((*scope, 8200), second, stale))
        with self.store.connection() as db:
            membership_before = db.execute(
                "SELECT monster_id,group_id FROM combat_group_members "
                "WHERE map_id=%s AND instance_id=%s ORDER BY monster_id",
                scope,
            ).fetchall()
        with patch("wakfu_server.combat_terrain.map_geometry", return_value=grid(64)):
            prepared = idle.validate_chunk(self.store, proposal)
        outcomes = idle.commit(
            self.store, groups, proposal, episode_current=True, prepared=prepared
        )
        self.assertEqual(
            outcomes,
            [
                dict(group_id=8100, status="applied"),
                dict(group_id=8200, status="skipped"),
            ],
        )
        self.assertEqual(
            idle.commit(
                self.store, groups, proposal, episode_current=True, prepared=prepared
            ),
            [],
        )
        self.assertEqual(
            idle.pending(self.store, epoch="idle-test", scope=scope, generation=1), []
        )
        with patch(
            "wakfu_server.monster_idle_distribution.plan",
            side_effect=AssertionError("Completed empty episode was planned twice"),
        ):
            for _ in range(3):
                self.assertEqual(
                    ecology_mobs.prepare(self.store, snapshot, limit=1), []
                )
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT group_id,members,revision FROM combat_groups "
                "WHERE map_id=%s AND instance_id=%s ORDER BY group_id",
                scope,
            ).fetchall()
            membership_after = db.execute(
                "SELECT monster_id,group_id FROM combat_group_members "
                "WHERE map_id=%s AND instance_id=%s ORDER BY monster_id",
                scope,
            ).fetchall()
        self.assertEqual(rows[0]["members"], moved)
        self.assertEqual(rows[0]["revision"], 1)
        self.assertEqual(rows[1]["members"], stale)
        self.assertEqual(membership_before, membership_after)
        for before, after in zip(members, rows[0]["members"]):
            self.assertEqual(
                {k: v for k, v in before.items() if k not in ("x", "y", "z")},
                {k: v for k, v in after.items() if k not in ("x", "y", "z")},
            )

        next_moves = [
            dict(
                group_id=8100,
                expected_members=moved,
                moved_members=[dict(m, y=20) for m in moved],
            )
        ]
        next_run = idle.freeze(
            self.store, epoch="idle-test", scope=scope, generation=2, moves=next_moves
        )
        self.assertNotEqual(run, next_run)
        next_proposal = idle.pending(
            self.store, epoch="idle-test", scope=scope, generation=2
        )[0]
        with patch("wakfu_server.combat_terrain.map_geometry", return_value=grid(64)):
            prepared = idle.validate_chunk(self.store, next_proposal)
        self.assertEqual(
            idle.commit(
                self.store,
                groups,
                next_proposal,
                episode_current=False,
                prepared=prepared,
            ),
            [],
        )
        self.assertEqual(
            idle.pending(self.store, epoch="idle-test", scope=scope, generation=2), []
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM monster_idle_distribution_runs WHERE id=%s",
                    (next_run,),
                ).fetchone()["status"],
                "cancelled",
            )
            durable = db.execute(
                "SELECT members,revision FROM combat_groups WHERE map_id=%s "
                "AND instance_id=%s AND group_id=8100",
                scope,
            ).fetchone()
        self.assertEqual(durable["members"], moved)
        self.assertEqual(durable["revision"], 1)
