"""All five original Gemlevolver offers through actual native machine authority."""
import struct
import uuid
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.exchange_machine import decode, purchase, station
from wakfu_server.inventory_items import grant
from wakfu_server.wire import proto_field


class GemlevolverPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "gemlin-" + uuid.uuid4().hex[:12], "local-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Gemlin Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=544,instance_id=0,x=30,y=6,z=0 WHERE id=%s",
                (self.character["id"],),
            )
        self.character = self.store.character(self.account, self.character["id"])
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )

    def item(self, reference):
        with self.store.connection() as db:
            occupied = {
                row["slot"]
                for row in db.execute(
                    "SELECT slot FROM inventory_items WHERE container=%s",
                    (self.container,),
                )
            }
        slot = next(slot for slot in range(30) if slot not in occupied)
        return grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=reference,
            quantity=1,
            container=self.container,
            slot=slot,
            allowed_references={reference},
        )

    def buy(self, offer):
        body = struct.pack(">iqihq", 211, 31682, offer, 1, self.character["id"])
        current = self.store.character(self.account, self.character["id"])
        authorized_station = station(current, decode(body))
        self.assertEqual(
            (211, 31682, 544),
            (
                authorized_station["catalog_id"],
                authorized_station["object_id"],
                authorized_station["map_id"],
            ),
        )
        return purchase(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            body,
            location=current,
            station=authorized_station,
        )

    def test_all_five_native_offers_consume_exact_costs_and_create_one_typed_pet(self):
        outputs = []
        for offset in range(5):
            with self.subTest(offer=6846 + offset, stone=26555 + offset):
                pet, stone = self.item(12237), self.item(26555 + offset)
                self.assertEqual(5, pet["pet"]["model_id"])
                result = self.buy(6846 + offset)
                self.assertEqual(6846 + offset, result["request"]["offer_id"])
                saved = self.reopen().character(self.account, self.character["id"])
                self.assertFalse(
                    {pet["uid"], stone["uid"]}
                    & {row["uid"] for row in saved["inventory_items"]}
                )
                evolved = [
                    row
                    for row in saved["inventory_items"]
                    if row["reference"] == 26673 + offset
                ]
                self.assertEqual(1, len(evolved))
                output = evolved[0]
                outputs.append(output["uid"])
                self.assertEqual(
                    (1, 203 + offset, 20, 25),
                    (
                        output["quantity"],
                        output["pet"]["model_id"],
                        output["pet"]["health"],
                        output["pet"]["maximum_level"],
                    ),
                )
                self.assertNotEqual(pet["uid"], output["uid"])
                with self.store.connection() as db:
                    self.assertIsNone(
                        db.execute(
                            "SELECT uid FROM inventory_pets WHERE uid=%s", (pet["uid"],)
                        ).fetchone()
                    )
                    self.assertEqual(
                        1,
                        db.execute(
                            "SELECT count(*) AS n FROM inventory_pets WHERE uid=%s",
                            (output["uid"],),
                        ).fetchone()["n"],
                    )
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT uid FROM inventory_pets WHERE uid=ANY(%s)", (outputs,)
            ).fetchall()
        self.assertEqual(5, len(rows))
        self.assertEqual(5, len({row["uid"] for row in rows}))

    def test_missing_stone_and_equipped_source_pet_leave_both_costs_unchanged(self):
        pet = self.item(12237)
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            self.buy(6846)
        stone = self.item(26555)
        equipment = proto_field(10, proto_field(8, pet["uid"]) + proto_field(16, 22))
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_builds SET equipment=%s WHERE character_id=%s AND build_index=0",
                (equipment, self.character["id"]),
            )
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            self.buy(6846)
        saved = self.reopen().character(self.account, self.character["id"])
        costs = {row["uid"]: row for row in saved["inventory_items"]}
        self.assertEqual(1, costs[pet["uid"]]["quantity"])
        self.assertEqual(5, costs[pet["uid"]]["pet"]["model_id"])
        self.assertEqual(1, costs[stone["uid"]]["quantity"])
        self.assertFalse(any(row["reference"] == 26673 for row in costs.values()))

    def test_typed_reward_initialization_failure_rolls_back_consumption_and_metadata(
        self,
    ):
        pet, stone = self.item(12237), self.item(26555)
        with patch(
            "wakfu_server.pet_inventory.initialize",
            side_effect=ValueError("Pet output initialization failed"),
        ):
            with self.assertRaisesRegex(ValueError, "Pet output initialization"):
                self.buy(6846)
        saved = self.reopen().character(self.account, self.character["id"])
        self.assertEqual(
            {pet["uid"], stone["uid"]}, {row["uid"] for row in saved["inventory_items"]}
        )
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT p.uid,p.model_id FROM inventory_pets p JOIN inventory_items i USING(uid) WHERE i.character_id=%s",
                (self.character["id"],),
            ).fetchall()
        self.assertEqual([{"uid": pet["uid"], "model_id": 5}], rows)
