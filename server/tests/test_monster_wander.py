"""World commits explicit worker moves; native planner coverage lives in Rust.

Retired planner assertions are covered by mob_geometry::legacy_wander_contract
and mob_geometry::tests (wire, cyclic paths, habitat, occupancy, batch bounds).
"""

from copy import deepcopy
from unittest.mock import patch
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from test_ecology_mobs_apply import FakeHarvests, FakeWorld, prepared_movement_packet
from wakfu_server import ecology_mobs, monster_wander
from wakfu_server.monster_wander import policy
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_group_store import PersistentGroups


class WanderTests(PostgresCase):
    configuration = dict(
        interval_seconds=1, move_probability=1.0, min_steps=1, max_steps=1, radius=20
    )

    def setUp(self):
        super().setUp()
        self.groups = PersistentGroups(self.store)
        self.before = [owned_instance(5525, 1, -200, map_id=1134, x=0, y=0, z=0)]
        self.key = self.groups.register(1134, 0, 500, self.before)
        self.world = FakeWorld([dict(id=88, map_id=1134, instance_id=0, x=3, y=0, z=0)])
        opcode, packet = prepared_movement_packet(-200, (0, 0, 0), (1, 0, 0))
        self.proposal = dict(
            kind="wander",
            world_epoch="wander-test",
            scope=[1134, 0],
            group_id=500,
            expected_members=self.before,
            moved_members=[dict(self.before[0], x=1)],
            packets=[[opcode, packet.hex()]],
            configuration=self.configuration,
        )

    def apply_prepared(self, harvests=None):
        with patch.object(monster_wander, "policy", return_value=self.configuration):
            return ecology_mobs.apply(
                self.store,
                self.groups,
                harvests or FakeHarvests(),
                self.world,
                self.proposal,
                world_epoch="wander-test",
            )

    def test_durable_positions_claim_race_and_postgres_cas(self):
        self.assertEqual(self.apply_prepared()["status"], "applied")
        recovered = PersistentGroups(self.reopen())
        self.assertEqual(recovered.available(1134, 0)[0]["members"][0]["x"], 1)
        self.assertEqual(self.apply_prepared()["status"], "stale_group")
        self.assertFalse(self.groups.move_members(self.key, self.before, self.before))
        self.assertEqual(self.groups.register_seed(1134, 0, 500, self.before), self.key)
        badseed = deepcopy(self.before)
        badseed[0]["id"] = -201
        with self.assertRaises(ValueError):
            self.groups.register_seed(1134, 0, 500, badseed)
        current = self.groups.available(1134, 0)[0]["members"]
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        lease, _ = self.groups.claim(self.key, "generation", fight)
        self.assertFalse(
            self.groups.move_members(self.key, current, [dict(current[0], x=0)])
        )
        self.assertEqual(len(self.world.emitted), 1)
        self.assertTrue(self.groups.finish(lease, defeated=False))

    def test_harvest_exclusion_and_fighting_neighbor_block_prepared_movement(self):
        self.assertEqual(
            self.apply_prepared(FakeHarvests({-200}))["status"], "harvesting"
        )
        neighbor = [owned_instance(5525, 1, -201, map_id=1134, x=1, y=0, z=0)]
        neighbor_key = self.groups.register(1134, 0, 501, neighbor)
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
        lease, _ = self.groups.claim(neighbor_key, "neighbor", fight)
        with patch.object(
            self.groups, "snapshot", wraps=self.groups.snapshot
        ) as snapshot:
            self.assertEqual(self.apply_prepared()["status"], "occupied")
        snapshot.assert_called_once_with(1134, 0)
        self.assertEqual(self.world.emitted, [])
        self.assertTrue(self.groups.finish(lease, defeated=False))

    def test_failed_group_position_cas_emits_no_packets(self):
        with patch.object(self.groups, "move_members", return_value=False) as cas:
            self.assertEqual(self.apply_prepared()["status"], "stale_group")
        cas.assert_called_once()
        self.assertEqual(self.world.emitted, [])
        self.assertEqual(
            list(self.groups.available(1134, 0)[0]["members"]), self.before
        )

    def test_requested_cadence_migration_preserves_custom_policies_and_is_idempotent(
        self,
    ):
        from pathlib import Path

        migration = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "327_monster_wander_requested_cadence.sql"
        ).read_text()
        previous = dict(
            interval_seconds=2,
            move_probability=0.6,
            min_steps=1,
            max_steps=3,
            radius=20,
        )
        requested = dict(previous, interval_seconds=1, max_steps=8)
        for before, expected in (
            (previous, requested),
            (requested, requested),
            (dict(previous, interval_seconds=4), dict(previous, interval_seconds=4)),
            (
                dict(previous, move_probability=0.35),
                dict(previous, move_probability=0.35),
            ),
        ):
            with self.subTest(before=before):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE settings SET value=%s WHERE name='monster_wander'",
                        (Jsonb(before),),
                    )
                    db.execute(migration)
                self.assertEqual(policy(self.store), expected)
                with self.store.connection() as db:
                    db.execute(migration)
                self.assertEqual(policy(self.reopen()), expected)

    def test_durable_policy_reloads_from_postgres_and_rejects_invalid_shapes(self):
        expected = {
            "interval_seconds": 1,
            "move_probability": 0.6,
            "min_steps": 1,
            "max_steps": 8,
            "radius": 20,
        }
        self.assertEqual(policy(self.store), expected)
        updated = dict(
            expected,
            interval_seconds=9,
            move_probability=0.6,
            min_steps=2,
            max_steps=4,
            radius=25,
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_wander'",
                (Jsonb(updated),),
            )
        self.assertEqual(policy(self.store), updated)

        invalid = [
            dict(updated, extra=True),
            dict(updated, interval_seconds="9"),
            dict(updated, interval_seconds=3601),
            dict(updated, move_probability=1.01),
            dict(updated, min_steps=0),
            dict(updated, min_steps=5, max_steps=4),
            dict(updated, radius=1001),
        ]
        for value in invalid:
            with self.subTest(policy=value):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE settings SET value=%s WHERE name='monster_wander'",
                        (Jsonb(value),),
                    )
                with self.assertRaises(ValueError):
                    policy(self.store)
