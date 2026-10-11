"""End-to-end fixed-product fishing harvest and durable refill cases."""
import struct
import unittest
import uuid
from datetime import timedelta

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.fishing_spots import refill
from wakfu_server.profession_store import ensure_learned
from wakfu_server.resource_collect import complete, prepare, reserve
from wakfu_server.wire import proto_field


class FishingHarvestPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.clock = [1_700_000_000.0]
        self.store.clock = lambda: self.clock[0]
        account = self.store.register(
            "fishing-" + uuid.uuid4().hex[:12], "local-password"
        )
        self.account = account["id"]
        self.character = self.store.create_character(self.account, "Fishing Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        ensure_learned(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            [75],
        )
        self.uid = 782_369

    def _install_active_target(self, reference, action_id, *, level=0):
        char = self.store.character(self.account, self.character["id"])
        if level:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE account_professions SET xp=%s WHERE account_id=%s AND profession_id=75",
                    (75 * level * level, self.account),
                )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO fishing_spot_slots(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,active,available_at,provenance) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,2,TRUE,%s,%s)",
                (
                    self.uid,
                    char["map_id"],
                    char["instance_id"],
                    char["x"],
                    char["y"],
                    char["z"],
                    reference,
                    self.store.now(),
                    Jsonb({"source": "fishing-harvest-test"}),
                ),
            )
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,2,%s)",
                (
                    self.uid,
                    char["map_id"],
                    char["instance_id"],
                    char["x"],
                    char["y"],
                    char["z"],
                    reference,
                    int(self.store.clock() * 1000),
                ),
            )
        body = (
            proto_field(8, action_id)
            + proto_field(16, char["x"] if char["x"] >= 0 else (1 << 64) + char["x"])
            + proto_field(24, char["y"] if char["y"] >= 0 else (1 << 64) + char["y"])
        )
        prepared = prepare(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            body,
            reachable=lambda _actor, _target: True,
        )
        ticket = reserve(self.store, self.account, self.generation, prepared)
        self.clock[0] += 6.1
        self.ticket = ticket
        self.result_body = struct.pack(">Bh", 2, 3)
        return complete(self.store, ticket, self.result_body)

    def _resource(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM planted_resources WHERE resource_uid=%s",
                (self.uid,),
            ).fetchone()

    def _slot(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM fishing_spot_slots WHERE resource_uid=%s",
                (self.uid,),
            ).fetchone()

    def _item_quantity(self, reference):
        character = self.store.character(self.account, self.character["id"])
        return sum(
            row["quantity"]
            for row in character["inventory_items"]
            if row["reference"] == reference
        )

    def _profession_xp(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=75",
                (self.account,),
            ).fetchone()["xp"]

    def test_native_cvf_zero_harvest_deletes_and_refills_same_uid(self):
        result = self._install_active_target(369, 1670)
        self.assertTrue(result["applied"])
        self.assertEqual(8105, result["outcome"]["item_reference"])
        self.assertEqual(0, result["outcome"]["stage"])
        self.assertEqual(50, result["outcome"]["xp"])
        self.assertEqual("fish_not_ecological", result["outcome"]["ecology"]["reason"])
        self.assertIsNone(self._resource())
        self.assertFalse(self._slot()["active"])
        self.assertEqual(
            self.store.now().replace(microsecond=0) + timedelta(seconds=300),
            self._slot()["available_at"].replace(microsecond=0),
        )
        before_item = self._item_quantity(8105)
        before_xp = self._profession_xp()
        replay = complete(self.store, self.ticket, self.result_body)
        self.assertEqual({"applied": False, "packets": [], "world_packets": []}, replay)
        self.assertEqual(before_item, self._item_quantity(8105))
        self.assertEqual(before_xp, self._profession_xp())
        self.assertEqual(0, refill(self.store))

        self.clock[0] += 300.1
        self.assertEqual(1, refill(self.store))
        self.assertEqual(self.uid, self._resource()["resource_uid"])
        self.assertEqual(2, self._resource()["stage"])
        self.assertTrue(self._slot()["active"])

    def test_native_cvf_one_reward_leaves_empty_stage_then_refills_in_place(self):
        result = self._install_active_target(563, 1404, level=80)
        self.assertTrue(result["applied"])
        self.assertEqual(18132, result["outcome"]["item_reference"])
        self.assertEqual(1, result["outcome"]["stage"])
        self.assertEqual(50, result["outcome"]["xp"])
        self.assertEqual("fish_not_ecological", result["outcome"]["ecology"]["reason"])
        self.assertEqual(self.uid, self._resource()["resource_uid"])
        self.assertEqual(1, self._resource()["stage"])
        self.assertFalse(self._slot()["active"])
        before_item = self._item_quantity(18132)
        before_xp = self._profession_xp()
        replay = complete(self.store, self.ticket, self.result_body)
        self.assertEqual({"applied": False, "packets": [], "world_packets": []}, replay)
        self.assertEqual(before_item, self._item_quantity(18132))
        self.assertEqual(before_xp, self._profession_xp())
        self.assertEqual(0, refill(self.store))

        self.clock[0] += 300.1
        self.assertEqual(1, refill(self.store))
        self.assertEqual(self.uid, self._resource()["resource_uid"])
        self.assertEqual(2, self._resource()["stage"])
        self.assertTrue(self._slot()["active"])


if __name__ == "__main__":
    unittest.main()
