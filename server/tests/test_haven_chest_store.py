"""Durable chest transactions in isolated PostgreSQL schemas only."""
from copy import deepcopy
import struct
from unittest.mock import patch
import uuid

from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from test_haven_chest import deposit_body, withdraw_body
from test_inventory_shards import sample_shard_state
from wakfu_server.haven_chest import deposit_all, load, transfer
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

    def _withdraw_as(self, character, container, reference, quantity):
        from wakfu_server.haven_chest import transfer

        saved = load(self.store, self.account, self.generation, character["id"])
        chest_slot = next(
            row["slot"]
            for row in saved["items"]
            if row["item"]["reference"] == reference
        )
        return transfer(
            self.store,
            self.account,
            self.generation,
            character["id"],
            12551,
            withdraw_body(
                character["id"],
                reference,
                quantity,
                container,
                slot=chest_slot,
                compartment=self.chest["id"],
            ),
            opening_token=self.opening,
            location=dict(
                character,
                map_id=9,
                instance_id=character["haven_bag"]["owner_id"],
            ),
        )

    @staticmethod
    def _stackable_template_binding(enum):
        from wakfu_server import exchange_rules
        from wakfu_server.inventory_move import STACKS
        from wakfu_server.quest_inventory import REFERENCES as CHARACTER_QUEST
        from wakfu_server.account_quest_inventory import (
            REFERENCES as ACCOUNT_QUEST,
        )

        quest_references = set(CHARACTER_QUEST) | set(ACCOUNT_QUEST)
        return next(
            reference
            for reference in sorted(STACKS)
            if reference not in quest_references
            and exchange_rules.ITEMS.get(str(reference), {})
            .get("binding_template", {})
            .get("enum")
            == enum
        )

    def test_mixed_template_bindings_keep_character_custody_across_shared_chest(self):
        from wakfu_server import exchange_rules

        character_ref = self._stackable_template_binding("BOUND_ON_PICKUP_TO_CHARACTER")
        account_ref = self._stackable_template_binding("BOUND_ON_PICKUP_TO_ACCOUNT")
        self.assertEqual(
            "BOUND_ON_PICKUP_TO_CHARACTER",
            exchange_rules.ITEMS[str(character_ref)]["binding_template"]["enum"],
        )
        self.assertEqual(
            "BOUND_ON_PICKUP_TO_ACCOUNT",
            exchange_rules.ITEMS[str(account_ref)]["binding_template"]["enum"],
        )
        character_bound = self.grant(reference=character_ref, quantity=1, slot=0)
        account_bound = self.grant(reference=account_ref, quantity=1, slot=1)
        ordinary = self.grant(reference=2504, quantity=3, slot=2)

        result = self.deposit_rows(
            [
                (character_bound["uid"], 0, 1),
                (account_bound["uid"], 1, 1),
                (ordinary["uid"], 2, 3),
            ]
        )
        self.assertTrue(result["applied"])
        self.assertEqual([], result["character"]["inventory_items"])
        entries = {row["item"]["uid"]: row for row in result["chest"]["items"]}
        self.assertEqual(
            self.char["id"],
            entries[character_bound["uid"]]["binding_owner_character_id"],
        )
        self.assertNotIn("binding_owner_character_id", entries[account_bound["uid"]])
        self.assertNotIn("binding_owner_character_id", entries[ordinary["uid"]])

        sibling = self.store.create_character(self.account, "Chest Binding Sibling")
        self.store.select_character(self.account, self.generation, sibling["id"])
        sibling = self.store.character(self.account, sibling["id"])
        sibling_container = sibling["inventory_containers"][0]["uid"]
        with self.assertRaisesRegex(ValueError, "Character-bound chest item"):
            self._withdraw_as(sibling, sibling_container, character_ref, 1)
        still_stored = load(self.store, self.account, self.generation, sibling["id"])
        self.assertIn(
            character_bound["uid"],
            {row["item"]["uid"] for row in still_stored["items"]},
        )

        shared_account_item = self._withdraw_as(
            sibling, sibling_container, account_ref, 1
        )
        self.assertTrue(shared_account_item["applied"])
        restored_account_item = next(
            row
            for row in shared_account_item["character"]["inventory_items"]
            if row["uid"] == account_bound["uid"]
        )
        self.assertEqual(account_ref, restored_account_item["reference"])
        shared_ordinary_item = self._withdraw_as(sibling, sibling_container, 2504, 3)
        self.assertEqual(
            ordinary["uid"],
            next(
                row["uid"]
                for row in shared_ordinary_item["character"]["inventory_items"]
                if row["reference"] == 2504
            ),
        )

        self.store.select_character(self.account, self.generation, self.char["id"])
        owner = self.store.character(self.account, self.char["id"])
        owner_result = self._withdraw_as(owner, self.container, character_ref, 1)
        restored_character_item = next(
            row
            for row in owner_result["character"]["inventory_items"]
            if row["uid"] == character_bound["uid"]
        )
        self.assertEqual(character_ref, restored_character_item["reference"])
        reopened = self.reopen()
        reopened.clock = self.store.clock
        persisted = load(reopened, self.account, self.generation, self.char["id"])
        self.assertEqual([], persisted["items"])

    def test_mixed_binding_bulk_deposit_rolls_back_every_source_on_storage_failure(
        self,
    ):
        character_ref = self._stackable_template_binding("BOUND_ON_PICKUP_TO_CHARACTER")
        account_ref = self._stackable_template_binding("BOUND_ON_PICKUP_TO_ACCOUNT")
        character_bound = self.grant(reference=character_ref, quantity=1, slot=0)
        account_bound = self.grant(reference=account_ref, quantity=1, slot=1)
        ordinary = self.grant(reference=2504, quantity=3, slot=2)
        before = deepcopy(self.store.character(self.account, self.char["id"]))
        chest_before = load(self.store, self.account, self.generation, self.char["id"])
        rows = [
            (character_bound["uid"], 0, 1),
            (account_bound["uid"], 1, 1),
            (ordinary["uid"], 2, 3),
        ]
        with patch(
            "wakfu_server.haven_chest._json",
            side_effect=RuntimeError("Injected mixed binding write failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "mixed binding"):
                self.deposit_rows(rows)
        after = self.store.character(self.account, self.char["id"])
        chest_after = load(self.store, self.account, self.generation, self.char["id"])
        self.assertEqual(before["inventory_items"], after["inventory_items"])
        self.assertEqual(chest_before, chest_after)
        self.assertEqual(
            {character_bound["uid"], account_bound["uid"], ordinary["uid"]},
            {row["uid"] for row in after["inventory_items"]},
        )

    def test_deposit_all_preserves_uid_metadata_and_skips_equipment_and_quest(self):
        from wakfu_server import quest_inventory
        from wakfu_server.wire import proto_field

        ordinary = self.grant(reference=2504, quantity=2, slot=0)
        equipped = self.grant(reference=13601, quantity=1, slot=1)
        with self.store.connection() as db:
            build = self.store.character(self.account, self.char["id"], db)["builds"][0]
            equipment = proto_field(
                10, proto_field(8, equipped["uid"]) + proto_field(16, 0)
            )
            db.execute(
                "INSERT INTO character_builds "
                "(character_id,build_index,sheet,equipment,deck,aptitudes) "
                "VALUES(%s,0,%s,%s,%s,%s) ON CONFLICT(character_id,build_index) "
                "DO UPDATE SET equipment=EXCLUDED.equipment",
                (
                    self.char["id"],
                    bytes.fromhex(build["sheet"]),
                    equipment,
                    bytes.fromhex(build["deck"]),
                    bytes.fromhex(build["aptitudes"]),
                ),
            )
            quest_inventory.grant(
                db, self.char["id"], min(quest_inventory.REFERENCES), 1
            )
            from wakfu_server.inventory_shards import save as save_shards

            save_shards(db, ordinary["uid"], sample_shard_state())
            db.execute(
                "INSERT INTO inventory_item_elements "
                "(uid,damage_elements,resistance_elements) VALUES(%s,6,0)",
                (ordinary["uid"],),
            )
            db.execute(
                "INSERT INTO inventory_item_appearances(uid,appearance_ref) "
                "VALUES(%s,2024)",
                (ordinary["uid"],),
            )
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) "
                "VALUES(%s,false,false)",
                (ordinary["uid"],),
            )
            db.execute(
                "INSERT INTO random_item_use_counters(source_uid,next_use) VALUES(%s,8)",
                (ordinary["uid"],),
            )
        shard_state = sample_shard_state()

        result = deposit_all(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            opening_token=self.opening,
            location=dict(
                self.char, map_id=9, instance_id=self.char["haven_bag"]["owner_id"]
            ),
        )

        self.assertTrue(result["applied"])
        self.assertEqual(
            [equipped["uid"]],
            [row["uid"] for row in result["character"]["inventory_items"]],
        )
        self.assertEqual(1, result["character"]["quest_items"][0]["quantity"])
        stored = next(
            row
            for row in result["chest"]["items"]
            if row["item"]["uid"] == ordinary["uid"]
        )
        self.assertEqual(2, stored["item"]["quantity"])
        self.assertEqual(
            shard_state, stored["metadata"]["inventory_item_shards"]["shard_state"]
        )
        self.assertEqual(
            6, stored["metadata"]["inventory_item_elements"]["damage_elements"]
        )
        self.assertEqual(
            {"uid": ordinary["uid"], "appearance_ref": 2024},
            stored["metadata"]["inventory_item_appearances"],
        )
        self.assertEqual(
            {"uid": ordinary["uid"], "unidentified": False, "socketed": False},
            stored["metadata"]["inventory_item_recycling_state"],
        )
        self.assertEqual(8, stored["metadata"]["random_item_use_counters"]["next_use"])

        withdrawn = self.withdraw(2504, 2)
        restored = next(
            row
            for row in withdrawn["character"]["inventory_items"]
            if row["uid"] == ordinary["uid"]
        )
        self.assertEqual(ordinary["uid"], restored["uid"])
        self.assertEqual(6, restored["damage_elements"])
        self.assertEqual(2024, restored["appearance_ref"])
        with self.store.connection() as db:
            self.assertEqual(
                8,
                db.execute(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (ordinary["uid"],),
                ).fetchone()["next_use"],
            )

    def test_deposit_all_searches_all_twenty_tabs_and_capacity_failure_is_atomic(self):
        from wakfu_server.items.inventory_move import STACKS

        first = self.grant(reference=2504, quantity=1, slot=0)
        maximum = STACKS[2504].get("native_maximum", STACKS[2504].get("maximum"))
        template = deepcopy(
            next(
                row
                for row in self.store.character(self.account, self.char["id"])[
                    "inventory_items"
                ]
                if row["uid"] == first["uid"]
            )
        )
        for key in ("character_id", "container", "slot"):
            template.pop(key, None)
        seed = [
            {
                "slot": slot,
                "item": dict(
                    template, uid=8_000_000_000_000_000_000 + slot, quantity=maximum
                ),
                "metadata": {},
            }
            for slot in range(1999)
        ]
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_haven_chests SET capacity=2000,items=%s WHERE account_id=%s",
                (Jsonb(seed), self.account),
            )
        result = deposit_all(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            opening_token=self.opening,
            location=dict(
                self.char, map_id=9, instance_id=self.char["haven_bag"]["owner_id"]
            ),
        )
        self.assertTrue(result["applied"])
        placed = next(
            row
            for row in result["chest"]["items"]
            if row["item"]["uid"] == first["uid"]
        )
        self.assertEqual(1999, placed["slot"])
        self.assertEqual(19, placed["slot"] // 100)

        second = self.grant(reference=2504, quantity=1, slot=1)
        full = deepcopy(result["chest"]["items"])
        full[-1] = {
            "slot": 1999,
            "item": dict(template, uid=8_000_000_000_000_001_999, quantity=maximum),
            "metadata": {},
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_haven_chests SET items=%s WHERE account_id=%s",
                (Jsonb(full), self.account),
            )
        chest_before = load(self.store, self.account, self.generation, self.char["id"])
        inventory_before = deepcopy(
            self.store.character(self.account, self.char["id"])["inventory_items"]
        )
        with self.store.connection() as db:
            receipts_before = db.execute(
                "SELECT count(*) AS n FROM account_haven_chest_receipts WHERE account_id=%s",
                (self.account,),
            ).fetchone()["n"]
        with self.assertRaisesRegex(ValueError, "full or invalid"):
            deposit_all(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                opening_token=uuid.uuid4(),
                location=dict(
                    self.char, map_id=9, instance_id=self.char["haven_bag"]["owner_id"]
                ),
            )
        self.assertEqual(
            inventory_before,
            self.store.character(self.account, self.char["id"])["inventory_items"],
        )
        self.assertEqual(
            chest_before,
            load(self.store, self.account, self.generation, self.char["id"]),
        )
        with self.store.connection() as db:
            receipts_after = db.execute(
                "SELECT count(*) AS n FROM account_haven_chest_receipts WHERE account_id=%s",
                (self.account,),
            ).fetchone()["n"]
        self.assertEqual(receipts_before, receipts_after)
        self.assertIn(second["uid"], {row["uid"] for row in inventory_before})

    def _native_multitab_body(self, rows):
        from wakfu_server.haven_chest_layout import compartments

        tabs = compartments(self.chest)
        result = [struct.pack(">h", len(rows))]
        for index, uid, quantity, slot in rows:
            identity = tabs[index]["id"].encode("ascii")
            result.append(struct.pack(">B", len(identity)) + identity)
            result.append(struct.pack(">hqhh", 1, uid, slot, quantity))
        return b"".join(result)

    def test_native_multitab_quick_expands_unmatched_rich_units_and_replays(self):
        import hashlib
        from wakfu_server.haven_chest_layout import compartments
        from wakfu_server.inventory_shards import save as save_shards

        tabs = compartments(self.chest)
        seed = self.grant(quantity=2)
        self.call(12038, deposit_body(seed["uid"], 1, compartment=tabs[0]["id"]))
        self.call(12038, deposit_body(seed["uid"], 1, compartment=tabs[1]["id"]))
        candidate = self.grant(quantity=2)
        rich = self.grant(reference=13601, quantity=1, slot=1)
        with self.store.connection() as db:
            save_shards(db, rich["uid"], sample_shard_state())
            db.execute(
                "INSERT INTO random_item_use_counters(source_uid,next_use) VALUES(%s,9)",
                (rich["uid"],),
            )
        body = self._native_multitab_body(
            [(0, candidate["uid"], 1, 0), (1, candidate["uid"], 1, 0)]
        )
        result = self.call(12038, body)
        self.assertTrue(result["applied"])
        self.assertFalse(result["character"]["inventory_items"])
        stored = next(
            row for row in result["chest"]["items"] if row["item"]["uid"] == rich["uid"]
        )
        self.assertEqual(
            sample_shard_state(),
            stored["metadata"]["inventory_item_shards"]["shard_state"],
        )
        self.assertEqual(9, stored["metadata"]["random_item_use_counters"]["next_use"])
        replay = self.call(12038, body)
        self.assertFalse(replay["applied"])
        self.assertEqual(result["chest"], replay["chest"])
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT revision FROM account_haven_chest_receipts WHERE account_id=%s "
                "AND request_hash=%s",
                (
                    self.account,
                    hashlib.sha256(struct.pack(">h", 12038) + body).digest(),
                ),
            ).fetchone()
        self.assertEqual(result["chest"]["revision"], receipt["revision"])

    def test_native_single_tab_preserves_manual_scope_and_invalid_bulk_rejects(self):
        candidate = self.grant(quantity=2)
        rich = self.grant(reference=13601, quantity=1, slot=1)
        result = self.call(
            12038, deposit_body(candidate["uid"], 1, compartment=self.chest["id"])
        )
        inventory = result["character"]["inventory_items"]
        self.assertEqual(
            {candidate["uid"], rich["uid"]}, {row["uid"] for row in inventory}
        )
        self.assertEqual(
            1,
            next(
                row["quantity"] for row in inventory if row["uid"] == candidate["uid"]
            ),
        )
        before = load(self.store, self.account, self.generation, self.char["id"])
        for rows in (
            [(0, candidate["uid"], 1, 1), (1, 123456789, 1, 0)],
            [(0, candidate["uid"], 1, 1), (1, candidate["uid"], 1, 0)],
            [(0, candidate["uid"], 1, 1), (1, rich["uid"], 1, 1000)],
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.call(12038, self._native_multitab_body(rows))
            self.assertEqual(
                before, load(self.store, self.account, self.generation, self.char["id"])
            )
            self.assertEqual(
                inventory,
                self.store.character(self.account, self.char["id"])["inventory_items"],
            )

    def test_native_multitab_expansion_capacity_failure_rolls_back_original_batch(self):
        from wakfu_server.inventory_move import STACKS

        candidate = self.grant(quantity=2)
        self.grant(reference=13601, quantity=1, slot=1)
        template = deepcopy(
            next(
                row
                for row in self.store.character(self.account, self.char["id"])[
                    "inventory_items"
                ]
                if row["uid"] == candidate["uid"]
            )
        )
        for key in ("character_id", "container", "slot"):
            template.pop(key, None)
        maximum = STACKS[2504].get("native_maximum", STACKS[2504].get("maximum"))
        seeded = [
            dict(
                slot=slot,
                item=dict(
                    template,
                    uid=8_000_000_000_000_000_000 + slot,
                    quantity=maximum - (1 if slot in (0, 100) else 0),
                ),
                metadata={},
            )
            for slot in range(2000)
        ]
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_haven_chests SET items=%s WHERE account_id=%s",
                (Jsonb(seeded), self.account),
            )
        before = load(self.store, self.account, self.generation, self.char["id"])
        inventory = deepcopy(
            self.store.character(self.account, self.char["id"])["inventory_items"]
        )
        body = self._native_multitab_body(
            [(0, candidate["uid"], 1, 0), (1, candidate["uid"], 1, 0)]
        )
        with self.assertRaisesRegex(ValueError, "full or invalid"):
            self.call(12038, body)
        self.assertEqual(
            before, load(self.store, self.account, self.generation, self.char["id"])
        )
        self.assertEqual(
            inventory,
            self.store.character(self.account, self.char["id"])["inventory_items"],
        )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM account_haven_chest_receipts WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["n"],
            )
