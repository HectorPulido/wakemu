"""Durable chest transactions in isolated PostgreSQL schemas only."""
from copy import deepcopy
from unittest.mock import patch
import uuid

from postgres_case import PostgresCase
from test_haven_chest import deposit_body, withdraw_body
from test_inventory_shards import sample_shard_state
from wakfu_server.haven_chest import load, transfer
from wakfu_server.inventory_items import grant


class HavenChestPersistenceTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1000
        self.account = self.store.register("chest-owner", "local-test-password")["id"]
        self.char = self.store.create_character(self.account, "Chest Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])
        self.container = self.char["inventory_containers"][0]["uid"]
        self.chest = load(self.store, self.account, self.generation, self.char["id"])
        self.opening = uuid.uuid4()

    def grant(self, reference=2504, quantity=9, slot=0):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=reference,
            quantity=quantity,
            container=self.container,
            slot=slot,
            allowed_references={reference},
        )

    def call(self, opcode, body, *, location=None, opening=None):
        location = location or dict(
            self.char, map_id=9, instance_id=self.char["haven_bag"]["owner_id"]
        )
        return transfer(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            opcode,
            body,
            opening_token=opening or self.opening,
            location=location,
        )

    def deposit(self, uid, quantity, slot=0):
        return self.call(
            12038, deposit_body(uid, quantity, slot=slot, compartment=self.chest["id"])
        )

    def withdraw(self, reference, quantity, slot=0, destination=-1):
        return self.call(
            12551,
            withdraw_body(
                self.char["id"],
                reference,
                quantity,
                self.container,
                slot=slot,
                destination=destination,
                compartment=self.chest["id"],
            ),
        )

    def test_partial_deposit_withdraw_and_reconnect_conserve_owned_quantity(self):
        item = self.grant()
        result = self.deposit(item["uid"], 4)
        self.assertEqual(result["character"]["inventory_items"][0]["quantity"], 5)
        self.assertEqual(result["chest"]["items"][0]["item"]["quantity"], 4)
        result = self.withdraw(2504, 2)
        self.assertEqual(result["character"]["inventory_items"][0]["quantity"], 7)
        self.assertEqual(result["chest"]["items"][0]["item"]["quantity"], 2)
        reopened = self.reopen()
        reopened.clock = self.store.clock
        chest = load(reopened, self.account, self.generation, self.char["id"])
        self.assertEqual(chest, result["chest"])
        self.assertEqual(
            reopened.character(self.account, self.char["id"])["inventory_items"],
            result["character"]["inventory_items"],
        )

    def test_retry_is_bounded_and_matches_current_revision(self):
        item = self.grant()
        first = self.deposit(item["uid"], 2)
        duplicate = self.deposit(item["uid"], 2)
        self.assertFalse(duplicate["applied"])
        self.assertEqual(first["chest"], duplicate["chest"])
        self.store.clock = lambda: 1004
        next_action = self.deposit(item["uid"], 2)
        self.assertTrue(next_action["applied"])
        self.assertEqual(next_action["character"]["inventory_items"][0]["quantity"], 5)
        self.assertEqual(next_action["chest"]["items"][0]["item"]["quantity"], 4)

    def test_second_character_uses_same_account_chest_and_restores_shards_elements(
        self,
    ):
        item = self.grant(reference=2869, quantity=1)
        shard = sample_shard_state()
        with self.store.connection() as db:
            from wakfu_server.inventory_shards import save

            save(db, item["uid"], shard)
        before = self.store.character(self.account, self.char["id"])["inventory_items"][
            0
        ]
        self.deposit(item["uid"], 1)
        second = self.store.create_character(self.account, "Chest Second")
        self.store.select_character(self.account, self.generation, second["id"])
        self.char, self.container = second, second["inventory_containers"][0]["uid"]
        shared = load(self.store, self.account, self.generation, self.char["id"])
        self.assertEqual(shared["id"], self.chest["id"])
        moved = self.withdraw(2869, 1)["character"]["inventory_items"][0]
        self.assertEqual(moved["uid"], before["uid"])
        self.assertEqual(moved["shard_state"], before["shard_state"])
        self.assertEqual(moved["damage_elements"], before["damage_elements"])
        self.assertEqual(moved["resistance_elements"], before["resistance_elements"])
        self.assertEqual(
            self.store.character(self.account, before["character_id"])[
                "inventory_items"
            ],
            [],
        )

    def test_pet_metadata_restores_exactly(self):
        item = self.grant(reference=18682, quantity=1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET xp=123,name=%s,revision=4 WHERE uid=%s",
                ("Chest Pet", item["uid"]),
            )
        before = self.store.character(self.account, self.char["id"])["inventory_items"][
            0
        ]["mount"]
        self.deposit(item["uid"], 1)
        moved = self.withdraw(18682, 1)["character"]["inventory_items"][0]
        self.assertEqual(moved["mount"], before)

    def test_storage_failure_rolls_back_inventory_and_chest(self):
        item = self.grant()
        before = deepcopy(self.store.character(self.account, self.char["id"]))
        with patch(
            "wakfu_server.haven_chest._json",
            side_effect=RuntimeError("Injected failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Injected"):
                self.deposit(item["uid"], 9)
        after = self.store.character(self.account, self.char["id"])
        self.assertEqual(after["inventory_items"], before["inventory_items"])
        self.assertEqual(
            load(self.store, self.account, self.generation, self.char["id"])["items"],
            [],
        )

    def test_foreign_location_and_actor_reject_without_mutation(self):
        item = self.grant()
        body = deposit_body(item["uid"], 3, compartment=self.chest["id"])
        for location in (
            dict(self.char, map_id=0, instance_id=0),
            dict(self.char, map_id=9, instance_id=99999),
        ):
            with self.assertRaises(ValueError):
                self.call(12038, body, location=location)
        foreign = withdraw_body(
            self.char["id"] + 1, 2504, 1, self.container, compartment=self.chest["id"]
        )
        with self.assertRaises(ValueError):
            self.call(12551, foreign)
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            9,
        )

    def test_equipment_in_any_build_cannot_be_deposited(self):
        item = self.grant(reference=2869, quantity=1)
        from wakfu_server.haven_chest import _equipped
        from wakfu_server.wire import proto_field

        character = self.store.character(self.account, self.char["id"])
        fake = deepcopy(character)
        fake["builds"]["secondary-test"] = dict(
            equipment=proto_field(10, proto_field(8, item["uid"])).hex()
        )
        self.assertIn(item["uid"], _equipped(fake))
        with patch.object(self.store, "character", return_value=fake):
            with self.assertRaisesRegex(ValueError, "every build"):
                self.deposit(item["uid"], 1)
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "uid"
            ],
            item["uid"],
        )
