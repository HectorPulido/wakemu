"""Isolated PostgreSQL lifecycle tests for fixed native fishing spots."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import threading
import unittest
from unittest.mock import patch

from psycopg.errors import CheckViolation
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.fishing_spots import deplete, install, refill, validate_placements
from wakfu_server.planting_runtime import Plantings


class FishingSpotPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.clock = [1_700_000_000.0]
        self.store.clock = lambda: self.clock[0]
        self.slot = dict(
            resource_uid=780_369,
            map_id=527,
            instance_id=0,
            x=-8,
            y=20,
            z=-4,
            resource_reference=369,
            stage=2,
            respawn_seconds=None,
            enabled=True,
            active=False,
            available_at=self.store.now(),
            provenance={"source": "native-fishing-review", "candidate": 1},
        )

    def _placement(self, **changes):
        return {
            key: self.slot[key]
            for key in (
                "resource_uid",
                "map_id",
                "instance_id",
                "x",
                "y",
                "z",
                "resource_reference",
                "stage",
                "respawn_seconds",
                "provenance",
            )
        } | changes

    def _surface(self, *, eligible_refs=(369,), approaches=((-9, 20, -3),)):
        return lambda _map, _x, _y, _z: {
            "ground_id": 18,
            "eligible_refs": frozenset(eligible_refs),
            "approaches": frozenset(approaches),
        }

    def _install(self, placements):
        with patch(
            "wakfu_server.fishing_navigation.surface", side_effect=self._surface()
        ):
            return install(self.store, placements)

    def _insert_slot(self, slot=None):
        values = dict(self.slot if slot is None else slot)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO fishing_spot_slots(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,respawn_seconds,enabled,active,available_at,provenance) "
                "VALUES(%(resource_uid)s,%(map_id)s,%(instance_id)s,%(x)s,%(y)s,%(z)s,"
                "%(resource_reference)s,%(stage)s,%(respawn_seconds)s,%(enabled)s,%(active)s,"
                "%(available_at)s,%(provenance)s)",
                {**values, "provenance": Jsonb(values["provenance"])},
            )

    def _slot(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM fishing_spot_slots WHERE resource_uid=%s",
                (self.slot["resource_uid"],),
            ).fetchone()

    def _resource(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM planted_resources WHERE resource_uid=%s",
                (self.slot["resource_uid"],),
            ).fetchone()

    def _outbox(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM planting_growth_outbox WHERE resource_uid=%s",
                (self.slot["resource_uid"],),
            ).fetchone()

    def test_install_idempotent_and_refill_restores_same_stage_one_uid(self):
        placement = self._placement()
        self.assertEqual(1, self._install([placement]))
        self.assertEqual(0, self._install([placement]))
        self.assertEqual(1, refill(self.store))
        self.assertEqual(0, refill(self.store))
        first = self._resource()
        self.assertEqual(self.slot["resource_uid"], first["resource_uid"])
        self.assertEqual(2, first["stage"])
        self.assertTrue(self._outbox()["resource"]["fishing_spawn"])
        self.assertTrue(self._slot()["active"])

        with self.store.connection() as db:
            self.assertTrue(deplete(db, dict(first), self.store.now()))
            db.execute(
                "UPDATE planted_resources SET stage=1 WHERE resource_uid=%s",
                (self.slot["resource_uid"],),
            )
        depleted = self._slot()
        self.assertFalse(depleted["active"])
        self.assertEqual(
            self.store.now() + timedelta(seconds=300), depleted["available_at"]
        )

        self.clock[0] += 300.1
        self.assertEqual(1, refill(self.store))
        revived = self._resource()
        self.assertEqual(first["resource_uid"], revived["resource_uid"])
        self.assertEqual(2, revived["stage"])
        self.assertNotIn("fishing_spawn", self._outbox()["resource"])
        self.assertTrue(self._slot()["active"])
        deliveries = Plantings(self.store).publish_growth(
            None,
            publish=lambda delivery: self.assertEqual(
                [12782], [opcode for opcode, _body in delivery["packets"]]
            ),
            resource_uid=self.slot["resource_uid"],
            limit=1,
        )
        self.assertEqual(1, len(deliveries))

    def test_refill_inserts_when_cv_f_zero_removed_the_resource(self):
        self._insert_slot()
        self.assertEqual(1, refill(self.store))
        resource = dict(self._resource())
        with self.store.connection() as db:
            self.assertTrue(deplete(db, resource, self.store.now()))
            db.execute(
                "DELETE FROM planted_resources WHERE resource_uid=%s",
                (self.slot["resource_uid"],),
            )
        self.clock[0] += 300.1
        self.assertEqual(1, refill(self.store))
        self.assertEqual(self.slot["resource_uid"], self._resource()["resource_uid"])
        self.assertEqual(2, self._resource()["stage"])
        self.assertTrue(self._outbox()["resource"]["fishing_spawn"])
        deliveries = Plantings(self.store).publish_growth(
            None,
            publish=lambda delivery: self.assertEqual(
                [13135], [opcode for opcode, _body in delivery["packets"]]
            ),
            resource_uid=self.slot["resource_uid"],
            limit=1,
        )
        self.assertEqual(1, len(deliveries))

    def test_cell_collision_retries_without_overwriting_other_resource(self):
        self._insert_slot()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) "
                "VALUES(780370,%s,0,%s,%s,%s,370,2,0)",
                (self.slot["map_id"], self.slot["x"], self.slot["y"], self.slot["z"]),
            )
        self.assertEqual(0, refill(self.store))
        self.assertFalse(self._slot()["active"])
        with self.store.connection() as db:
            db.execute("DELETE FROM planted_resources WHERE resource_uid=780370")
        self.assertEqual(1, refill(self.store))
        self.assertTrue(self._slot()["active"])

    def test_concurrent_refill_claims_a_spot_once(self):
        self._insert_slot()
        start = threading.Barrier(2)

        def run():
            start.wait(timeout=5)
            return refill(self.store)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(1, sum(results))
        self.assertTrue(self._slot()["active"])
        self.assertEqual(
            1, self._resource()["resource_uid"] == self.slot["resource_uid"]
        )

    def test_install_requires_native_or_explicit_fish_ground_policy(self):
        placement = self._placement()
        incompatible = self._surface(eligible_refs=(370,))
        with patch("wakfu_server.fishing_navigation.surface", side_effect=incompatible):
            with self.assertRaisesRegex(ValueError, "incompatible with native terrain"):
                validate_placements([placement])

        local = {
            **placement,
            "provenance": {
                **placement["provenance"],
                "species_ground_policy": "local-fishing-ground-fallback",
            },
        }
        with patch("wakfu_server.fishing_navigation.surface", side_effect=incompatible):
            self.assertEqual([local], validate_placements([local]))

    def test_install_rejects_empty_or_unsupported_native_stages(self):
        with patch(
            "wakfu_server.fishing_navigation.surface", side_effect=self._surface()
        ):
            with self.assertRaisesRegex(ValueError, "active native stage"):
                validate_placements([self._placement(stage=1)])
            with self.assertRaisesRegex(ValueError, "supported native fishing action"):
                validate_placements([self._placement(resource_reference=306, stage=2)])

    def test_slot_stage_one_is_only_an_exhausted_resource_not_a_target(self):
        from wakfu_server.fishing_spots import _supported_stage

        with self.assertRaisesRegex(ValueError, "supported native fishing action"):
            _supported_stage(369, 1)
        with self.assertRaises(CheckViolation):
            self._insert_slot(dict(self.slot, stage=1))


if __name__ == "__main__":
    unittest.main()
