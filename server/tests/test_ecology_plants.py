"""Read-only growth proposals and authoritative single-row application."""
import json
import unittest
from unittest.mock import Mock

from postgres_case import PostgresCase
from wakfu_server import ecology_plants
from wakfu_server.planting_runtime import Plantings
from wakfu_server.combat_groups import Groups


class EcologyPlantPlanTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1000.0
        self.runtime = Plantings(self.store)
        self.runtime.ecology_world_epoch = "boot-a"
        self.groups = Groups()
        ecology_plants._CURSORS.clear()
        self.snapshot = dict(
            world_epoch="boot-a",
            now_ms=1000000,
            players=[],
            excluded_ids=[],
            locations=[],
            planning_tick=1,
        )
        with self.store.connection() as db:
            self.policy = db.execute(
                "SELECT * FROM resource_growth_transitions WHERE resource_reference=60 "
                "AND from_stage=1"
            ).fetchone()
            self.assertIsNotNone(self.policy)
            db.execute(
                "UPDATE resource_growth_transitions SET probability=1 "
                "WHERE resource_reference=60 AND from_stage=1"
            )

    def add(self, uid):
        resource = dict(
            resource_uid=uid,
            map_id=1134,
            instance_id=0,
            x=uid,
            y=uid + 1,
            z=0,
            resource_reference=60,
            stage=1,
            creation_time=1000000 - self.policy["delay_ms"] - 1,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource.values()),
            )
        return resource

    def row(self, uid):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM planted_resources WHERE resource_uid=%s", (uid,)
            ).fetchone()

    def test_prepare_is_read_only_bounded_and_json_safe(self):
        resource = self.add(9001)
        self.add(9002)
        plans = ecology_plants.prepare(self.store, self.snapshot, limit=1)
        self.assertEqual(len(plans), 1)
        json.dumps(plans)
        self.assertEqual(dict(self.row(9001)), resource)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute("SELECT 1 FROM planting_growth_outbox").fetchone()
            )

    def test_apply_advances_once_and_publishes_only_proposed_resource(self):
        self.add(9011)
        self.add(9012)
        plan = ecology_plants.prepare(self.store, self.snapshot, limit=1)[0]
        emitted = []
        result = ecology_plants.apply(
            self.runtime,
            self.groups,
            plan,
            authorize_spawn=lambda _: True,
            publish=emitted.append,
        )
        self.assertTrue(result["applied"])
        self.assertEqual(self.row(9011)["stage"], self.policy["to_stage"])
        self.assertEqual(self.row(9012)["stage"], 1)
        again = ecology_plants.apply(
            self.runtime,
            self.groups,
            plan,
            authorize_spawn=lambda _: True,
            publish=emitted.append,
        )
        self.assertFalse(again["applied"])
        self.assertEqual(len(emitted), 1)

    def test_changed_resource_and_changed_policy_reject_stale_plan(self):
        self.add(9021)
        plan = ecology_plants.prepare(self.store, self.snapshot, limit=1)[0]
        with self.store.connection() as db:
            db.execute(
                "UPDATE resource_growth_transitions SET probability=0.5 "
                "WHERE resource_reference=60 AND from_stage=1"
            )
        emitted = []
        result = ecology_plants.apply(
            self.runtime,
            self.groups,
            plan,
            authorize_spawn=lambda _: True,
            publish=emitted.append,
        )
        self.assertFalse(result["applied"])
        self.assertEqual(self.row(9021)["stage"], 1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE planted_resources SET creation_time=creation_time+1 "
                "WHERE resource_uid=9021"
            )
        ecology_plants.apply(
            self.runtime,
            self.groups,
            plan,
            authorize_spawn=lambda _: True,
            publish=emitted.append,
        )
        self.assertEqual(emitted, [])

    def test_committed_outbox_recovers_after_failed_delivery(self):
        self.add(9025)
        plan = ecology_plants.prepare(self.store, self.snapshot, limit=1)[0]

        def failed(_):
            raise RuntimeError("lost delivery")

        with self.assertRaises(RuntimeError):
            ecology_plants.apply(
                self.runtime,
                self.groups,
                plan,
                authorize_spawn=lambda _: True,
                publish=failed,
            )
        pending = ecology_plants.prepare(self.store, self.snapshot)
        recovery = next(p for p in pending if p["kind"] == "growth_publish")
        emitted = []
        result = ecology_plants.apply(
            self.runtime,
            self.groups,
            recovery,
            authorize_spawn=lambda _: True,
            publish=emitted.append,
        )
        self.assertTrue(result["applied"])
        self.assertEqual(len(emitted), 1)

    def test_world_epoch_rejects_without_database_mutation(self):
        self.add(9031)
        plan = ecology_plants.prepare(self.store, self.snapshot, limit=1)[0]
        self.runtime.ecology_world_epoch = "boot-b"
        result = ecology_plants.apply(
            self.runtime,
            self.groups,
            plan,
            authorize_spawn=lambda _: True,
            publish=Mock(),
        )
        self.assertEqual(result["reason"], "stale_world_epoch")
        self.assertEqual(self.row(9031)["stage"], 1)

    def test_keyset_cursor_reaches_later_due_resources_and_wraps(self):
        self.add(9041)
        self.add(9042)
        plans = [
            ecology_plants.prepare(self.store, self.snapshot, limit=1)[0]
            for _ in range(3)
        ]
        self.assertEqual(
            [p["expected"]["resource_uid"] for p in plans], [9041, 9042, 9041]
        )

    def test_publication_receives_its_own_quota_with_flora_backlog(self):
        from psycopg.types.json import Jsonb

        resource = self.add(9051)
        for uid in range(9052, 9058):
            self.add(uid)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) "
                "VALUES(%s,%s,NULL)",
                (9051, Jsonb(resource)),
            )
        plans = ecology_plants.prepare(self.store, self.snapshot, limit=4)
        self.assertIn("growth_publish", [p["kind"] for p in plans])
        self.assertLessEqual(len(plans), 4)

    def test_invalid_batch_and_malformed_resource_rejected(self):
        with self.assertRaises(ValueError):
            ecology_plants.prepare(self.store, self.snapshot, limit=0)
        with self.assertRaises(ValueError):
            ecology_plants.apply(
                self.runtime,
                self.groups,
                dict(world_epoch="boot-a", kind="resource_growth", expected={}),
                authorize_spawn=lambda _: True,
                publish=Mock(),
            )
