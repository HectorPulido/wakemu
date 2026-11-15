"""World growth admission/CAS; autonomous planner contracts are Rust tests."""

import unittest
from unittest.mock import Mock

from postgres_case import PostgresCase
from wakfu_server import ecology_plants
from wakfu_server.planting_runtime import Plantings
from wakfu_server.combat_groups import Groups


class EcologyPlantApplyTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1000.0
        self.runtime = Plantings(self.store)
        self.runtime.ecology_world_epoch = "boot-a"
        self.groups = Groups()
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

    def proposal(self, resource):
        # Explicit external-planner fixture. This helper makes no planning query.
        return dict(
            kind="resource_growth",
            world_epoch="boot-a",
            expected=dict(resource),
            transition=[self.policy["to_stage"], self.policy["delay_ms"], 1.0],
            member=None,
        )

    def test_apply_advances_once_and_publishes_only_proposed_resource(self):
        resource = self.add(9011)
        self.add(9012)
        plan = self.proposal(resource)
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
        resource = self.add(9021)
        plan = self.proposal(resource)
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
        resource = self.add(9025)
        plan = self.proposal(resource)

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
        with self.store.connection() as db:
            pending = db.execute(
                "SELECT resource_uid FROM planting_growth_outbox WHERE NOT published"
            ).fetchall()
        self.assertEqual([row["resource_uid"] for row in pending], [9025])
        recovery = dict(kind="growth_publish", world_epoch="boot-a", resource_uid=9025)
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
        resource = self.add(9031)
        plan = self.proposal(resource)
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

    def test_malformed_resource_rejected_before_world_mutation(self):
        with self.assertRaises(ValueError):
            ecology_plants.apply(
                self.runtime,
                self.groups,
                dict(world_epoch="boot-a", kind="resource_growth", expected={}),
                authorize_spawn=lambda _: True,
                publish=Mock(),
            )
