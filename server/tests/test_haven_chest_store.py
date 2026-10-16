"""Durable chest transactions in isolated PostgreSQL schemas only."""
from copy import deepcopy
import struct
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

    def call(self, opcode, body, *, location=None, opening=None, store=None):
        location = location or dict(
            self.char, map_id=9, instance_id=self.char["haven_bag"]["owner_id"]
        )
        return transfer(
            self.store if store is None else store,
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

    def deposit_rows(self, rows):
        identity = self.chest["id"].encode("ascii")
        body = (
            struct.pack(">hB", 1, len(identity))
            + identity
            + struct.pack(">h", len(rows))
            + b"".join(struct.pack(">qhh", *row) for row in rows)
        )
        return self.call(12038, body)

    def character_with_equipped_uid(self, uid, *, build_index=2):
        from wakfu_server.wire import proto_field

        character = deepcopy(self.store.character(self.account, self.char["id"]))
        equipment = proto_field(10, proto_field(8, uid) + proto_field(16, 16))
        character["builds"][build_index] = {"equipment": equipment.hex()}
        return character

    def active_hero_with_item(self, *, reference=2504, quantity=5, slot=0):
        from wakfu_server.characters import heroes

        hero = self.store.create_character(self.account, "Chest Active Hero")
        heroes.add(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            hero["id"],
        )
        self.store.select_character(self.account, self.generation, hero["id"])
        selected_hero = self.store.character(self.account, hero["id"])
        container = selected_hero["inventory_containers"][0]["uid"]
        item = grant(
            self.store,
            self.account,
            self.generation,
            hero["id"],
            reference=reference,
            quantity=quantity,
            container=container,
            slot=slot,
            allowed_references={reference},
        )
        self.store.select_character(self.account, self.generation, self.char["id"])
        return hero, container, item

    def withdraw_from(
        self, actor_id, container, reference, quantity, *, slot=0, store=None
    ):
        return self.call(
            12551,
            withdraw_body(
                actor_id,
                reference,
                quantity,
                container,
                slot=slot,
                destination=-1,
                compartment=self.chest["id"],
            ),
            store=store,
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

    def test_twentieth_tab_relocation_and_withdrawal_survive_reconnect(self):
        import struct
        from wakfu_server.haven_chest_layout import compartments

        item = self.grant(quantity=9)
        self.deposit(item["uid"], 9, slot=2)
        last_tab = compartments(self.chest)[19]["id"].encode("ascii")
        first_tab = self.chest["id"].encode("ascii")
        relocation = (
            bytes((len(first_tab),))
            + first_tab
            + struct.pack(">hhhB", 1, 2, 9, len(last_tab))
            + last_tab
            + struct.pack(">i", 5)
        )
        relocated = self.call(13050, relocation)
        self.assertEqual(relocated["character"]["inventory_items"], [])
        reopened = self.reopen()
        reopened.clock = self.store.clock
        saved = load(reopened, self.account, self.generation, self.char["id"])
        self.assertEqual(saved["capacity"], 2000)
        self.assertEqual(saved["items"][0]["slot"], 1905)
        self.assertEqual(saved["items"][0]["item"]["uid"], item["uid"])
        result = self.call(
            12551,
            withdraw_body(
                self.char["id"],
                2504,
                4,
                self.container,
                slot=5,
                destination=0,
                compartment=last_tab.decode("ascii"),
            ),
        )
        saved = load(reopened, self.account, self.generation, self.char["id"])
        owned = reopened.character(self.account, self.char["id"])["inventory_items"]
        self.assertEqual(saved, result["chest"])
        self.assertEqual(saved["items"][0]["item"]["quantity"], 5)
        self.assertEqual(sum(row["quantity"] for row in owned), 4)
        self.assertEqual(saved["items"][0]["item"]["uid"], item["uid"])

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
        before_revision = self.chest["revision"]
        with patch.object(self.store, "character", return_value=fake):
            result = self.deposit(item["uid"], 1)
        self.assertFalse(result["applied"])
        self.assertEqual(result["skipped_equipped"], [item["uid"]])
        self.assertEqual(result["chest"]["revision"], before_revision)
        self.assertEqual(result["chest"]["items"], [])
        current = self.store.character(self.account, self.char["id"])
        self.assertEqual(current["inventory_items"][0]["uid"], item["uid"])
        with self.store.connection() as db:
            receipts = db.execute(
                "SELECT count(*) AS n FROM account_haven_chest_receipts "
                "WHERE account_id=%s AND generation=%s",
                (self.account, self.generation),
            ).fetchone()["n"]
        self.assertEqual(receipts, 0)

    def test_mixed_equipped_and_ordinary_deposit_replays_after_reconnect(self):
        equipped = self.grant(reference=2504, quantity=4, slot=0)
        ordinary = self.grant(reference=2504, quantity=5, slot=1)
        character = self.character_with_equipped_uid(equipped["uid"], build_index=0)
        before_revision = self.chest["revision"]
        rows = [(equipped["uid"], 0, 4), (ordinary["uid"], 1, 5)]
        with patch.object(self.store, "character", return_value=character):
            result = self.deposit_rows(rows)

        self.assertTrue(result["applied"])
        self.assertEqual(result["skipped_equipped"], [equipped["uid"]])
        self.assertEqual(result["chest"]["revision"], before_revision + 1)
        self.assertEqual(
            [row["item"]["uid"] for row in result["chest"]["items"]],
            [ordinary["uid"]],
        )
        current = self.store.character(self.account, self.char["id"])
        self.assertEqual(
            [(row["uid"], row["quantity"]) for row in current["inventory_items"]],
            [(equipped["uid"], 4)],
        )

        reopened = self.reopen()
        reopened.clock = self.store.clock
        saved_chest = load(reopened, self.account, self.generation, self.char["id"])
        saved_character = reopened.character(self.account, self.char["id"])
        self.assertEqual(saved_chest, result["chest"])
        self.assertEqual(
            [
                (row["uid"], row["quantity"])
                for row in saved_character["inventory_items"]
            ],
            [(equipped["uid"], 4)],
        )
        from wakfu_server.haven_chest import transfer

        replay = transfer(
            reopened,
            self.account,
            self.generation,
            self.char["id"],
            12038,
            self.deposit_body_rows(rows),
            opening_token=self.opening,
            location=dict(
                self.char, map_id=9, instance_id=self.char["haven_bag"]["owner_id"]
            ),
        )
        self.assertFalse(replay["applied"])
        self.assertEqual(replay["chest"], saved_chest)
        self.assertEqual(
            reopened.character(self.account, self.char["id"])["inventory_items"],
            saved_character["inventory_items"],
        )

    def test_active_hero_deposit_withdraw_replay_and_reconnect_keep_main_selected(self):
        hero, container, item = self.active_hero_with_item(quantity=6)
        self.assertTrue(
            self.store.current_character_session(
                self.account, self.generation, self.char["id"]
            )
        )
        deposited = self.deposit(item["uid"], 6)
        self.assertEqual(deposited["character"]["id"], self.char["id"])
        self.assertEqual(
            [owner["id"] for owner in deposited["inventory_characters"]],
            [hero["id"]],
        )
        self.assertEqual(deposited["chest"]["items"][0]["item"]["uid"], item["uid"])
        self.assertEqual(
            self.store.character(self.account, hero["id"])["inventory_items"], []
        )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"], []
        )

        deposit_replay = self.deposit(item["uid"], 6)
        self.assertFalse(deposit_replay["applied"])
        self.assertEqual(deposit_replay["character"]["id"], self.char["id"])
        self.assertEqual(
            {owner["id"] for owner in deposit_replay["inventory_characters"]},
            {self.char["id"], hero["id"]},
        )

        withdrawn = self.withdraw_from(hero["id"], container, 2504, 6)
        self.assertTrue(withdrawn["applied"])
        self.assertEqual(withdrawn["character"]["id"], self.char["id"])
        self.assertEqual(
            [owner["id"] for owner in withdrawn["inventory_characters"]],
            [hero["id"]],
        )
        self.assertEqual(
            [
                (row["uid"], row["quantity"])
                for row in self.store.character(self.account, hero["id"])[
                    "inventory_items"
                ]
            ],
            [(item["uid"], 6)],
        )
        self.assertTrue(
            self.store.current_character_session(
                self.account, self.generation, self.char["id"]
            )
        )
        self.assertFalse(
            self.store.current_character_session(
                self.account, self.generation, hero["id"]
            )
        )

        reopened = self.reopen()
        reopened.clock = self.store.clock
        saved = load(reopened, self.account, self.generation, self.char["id"])
        replay = self.withdraw_from(hero["id"], container, 2504, 6, store=reopened)
        self.assertFalse(replay["applied"])
        self.assertEqual(saved["items"], [])
        self.assertEqual(replay["character"]["id"], self.char["id"])
        self.assertEqual(
            {owner["id"] for owner in replay["inventory_characters"]},
            {self.char["id"], hero["id"]},
        )
        self.assertEqual(
            reopened.character(self.account, hero["id"])["inventory_items"][0]["uid"],
            item["uid"],
        )

    def test_active_hero_mixed_equipped_deposit_mutates_only_ordinary_uid(self):
        from wakfu_server.wire import proto_field

        hero, _, equipped = self.active_hero_with_item(quantity=3, slot=0)
        self.store.select_character(self.account, self.generation, hero["id"])
        hero_row = self.store.character(self.account, hero["id"])
        container = hero_row["inventory_containers"][0]["uid"]
        ordinary = grant(
            self.store,
            self.account,
            self.generation,
            hero["id"],
            reference=2504,
            quantity=4,
            container=container,
            slot=1,
            allowed_references={2504},
        )
        self.store.select_character(self.account, self.generation, self.char["id"])
        original = self.store.character

        def character_with_equipped_hero(account_id, character_id, db=None):
            current = original(account_id, character_id, db)
            if character_id == hero["id"]:
                equipment = proto_field(
                    10, proto_field(8, equipped["uid"]) + proto_field(16, 16)
                )
                current["builds"][0] = {"equipment": equipment.hex()}
            return current

        rows = [(equipped["uid"], 0, 3), (ordinary["uid"], 1, 4)]
        with patch.object(
            self.store, "character", side_effect=character_with_equipped_hero
        ):
            result = self.deposit_rows(rows)
        self.assertTrue(result["applied"])
        self.assertEqual(result["character"]["id"], self.char["id"])
        self.assertEqual(
            [owner["id"] for owner in result["inventory_characters"]], [hero["id"]]
        )
        self.assertEqual(result["skipped_equipped"], [equipped["uid"]])
        self.assertEqual(
            [row["item"]["uid"] for row in result["chest"]["items"]],
            [ordinary["uid"]],
        )
        current_hero = self.store.character(self.account, hero["id"])
        self.assertEqual(
            [(row["uid"], row["quantity"]) for row in current_hero["inventory_items"]],
            [(equipped["uid"], 3)],
        )
        reopened = self.reopen()
        reopened.clock = self.store.clock
        replay = transfer(
            reopened,
            self.account,
            self.generation,
            self.char["id"],
            12038,
            self.deposit_body_rows(rows),
            opening_token=self.opening,
            location=dict(
                self.char, map_id=9, instance_id=self.char["haven_bag"]["owner_id"]
            ),
        )
        self.assertFalse(replay["applied"])
        self.assertEqual(replay["chest"], result["chest"])
        self.assertEqual(
            {owner["id"] for owner in replay["inventory_characters"]},
            {self.char["id"], hero["id"]},
        )
        self.assertEqual(
            reopened.character(self.account, hero["id"])["inventory_items"][0]["uid"],
            equipped["uid"],
        )

    def test_active_hero_deposit_can_split_one_uid_across_chest_slots(self):
        hero, _, item = self.active_hero_with_item(quantity=7)
        result = self.deposit_rows([(item["uid"], 0, 2), (item["uid"], 1, 5)])
        self.assertTrue(result["applied"])
        self.assertEqual(result["character"]["id"], self.char["id"])
        self.assertEqual(
            [owner["id"] for owner in result["inventory_characters"]], [hero["id"]]
        )
        self.assertEqual(
            sorted(row["item"]["quantity"] for row in result["chest"]["items"]),
            [2, 5],
        )
        self.assertEqual(
            sum(row["item"]["quantity"] for row in result["chest"]["items"]), 7
        )
        self.assertEqual(
            self.store.character(self.account, hero["id"])["inventory_items"], []
        )

    def test_inactive_and_foreign_hero_uids_cannot_enter_chest(self):
        inactive = self.store.create_character(self.account, "Chest Inactive Hero")
        self.store.select_character(self.account, self.generation, inactive["id"])
        container = inactive["inventory_containers"][0]["uid"]
        inactive_item = grant(
            self.store,
            self.account,
            self.generation,
            inactive["id"],
            reference=2504,
            quantity=1,
            container=container,
            slot=0,
            allowed_references={2504},
        )
        foreign_account = self.store.register(
            "foreign-chest-owner", "local-test-password"
        )["id"]
        foreign = self.store.create_character(foreign_account, "Foreign Chest Owner")
        foreign_generation = self.store.begin_session(foreign_account)
        self.store.select_character(foreign_account, foreign_generation, foreign["id"])
        foreign_container = foreign["inventory_containers"][0]["uid"]
        foreign_item = grant(
            self.store,
            foreign_account,
            foreign_generation,
            foreign["id"],
            reference=2504,
            quantity=1,
            container=foreign_container,
            slot=0,
            allowed_references={2504},
        )
        self.store.select_character(self.account, self.generation, self.char["id"])
        before_revision = load(
            self.store, self.account, self.generation, self.char["id"]
        )["revision"]

        for item in (inactive_item, foreign_item):
            with self.subTest(uid=item["uid"]):
                with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
                    self.deposit(item["uid"], 1)
        self.assertEqual(
            load(self.store, self.account, self.generation, self.char["id"])[
                "revision"
            ],
            before_revision,
        )
        self.assertEqual(
            self.store.character(self.account, inactive["id"])["inventory_items"][0][
                "uid"
            ],
            inactive_item["uid"],
        )

    def deposit_body_rows(self, rows):
        identity = self.chest["id"].encode("ascii")
        return (
            struct.pack(">hB", 1, len(identity))
            + identity
            + struct.pack(">h", len(rows))
            + b"".join(struct.pack(">qhh", *row) for row in rows)
        )
