import struct
import unittest
from pathlib import Path

from postgres_case import PostgresCase
from wakfu_server.items import quest_inventory


class QuestInventoryWireTests(unittest.TestCase):
    def test_native_properties_classify_tokens_without_account_artifacts(self):
        self.assertEqual(len(quest_inventory.REFERENCES), 377)
        self.assertIn(12686, quest_inventory.REFERENCES)
        self.assertIn(23838, quest_inventory.REFERENCES)
        self.assertNotIn(18722, quest_inventory.REFERENCES)
        self.assertNotIn(2021, quest_inventory.REFERENCES)

    def test_native_section_and_event_protocol_are_owned_absolute_quantities(self):
        before = dict(id=7, quest_items=[])
        first = dict(
            id=7, quest_items=[dict(character_id=7, reference=12686, quantity=20)]
        )
        second = dict(
            id=7, quest_items=[dict(character_id=7, reference=12686, quantity=25)]
        )
        self.assertEqual(
            quest_inventory.section(first), struct.pack(">Hih", 1, 12686, 20) + bytes(4)
        )
        self.assertEqual(
            quest_inventory.changes(before, first),
            [(13879, struct.pack(">qBih", 7, 0, 12686, 20))],
        )
        self.assertEqual(
            quest_inventory.changes(first, second),
            [(13879, struct.pack(">qBih", 7, 2, 12686, 25))],
        )
        self.assertEqual(quest_inventory.changes(first, first), [])
        self.assertEqual(
            quest_inventory.changes(first, before),
            [(13879, struct.pack(">qBi", 7, 1, 12686))],
        )
        self.assertEqual(quest_inventory.quantity(first, (12686, 2**32 + 12686)), 40)
        with self.assertRaises(ValueError):
            quest_inventory.section(dict(id=8, quest_items=first["quest_items"]))


class QuestInventoryPersistenceTests(PostgresCase):
    def _owner(self):
        account = self.store.register("quest-tokens", "local-password")["id"]
        character = self.store.create_character(account, "Token Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        return account, character, generation

    def test_public_grant_ignores_bag_capacity_stacks_and_survives_reopen(self):
        from wakfu_server.inventory_items import grant, insertion

        account, character, generation = self._owner()
        with self.store.connection() as db:
            for bag in character["inventory_containers"]:
                for slot in range(bag["capacity"]):
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                        "VALUES(%s,2021,1,%s,%s)",
                        (character["id"], bag["uid"], slot),
                    )
        for amount in (20, 5):
            item = grant(
                self.store,
                account,
                generation,
                character["id"],
                reference=12686,
                quantity=amount,
                container=character["inventory_containers"][0]["uid"],
                slot=0,
                allowed_references={12686},
            )
            self.assertEqual(insertion(item)[0], 13879)
        saved = self.reopen().character(account, character["id"])
        self.assertEqual(
            saved["quest_items"],
            [dict(character_id=character["id"], reference=12686, quantity=25)],
        )
        self.assertEqual(len(saved["inventory_items"]), 34)
        with self.store.connection() as db:
            with self.assertRaises(ValueError):
                quest_inventory.grant(db, character["id"], 12686, 9999)
        self.assertEqual(
            self.store.character(account, character["id"])["quest_items"][0][
                "quantity"
            ],
            25,
        )

    def test_migration_preserves_existing_bag_quantities_and_removes_physical_slots(
        self,
    ):
        account, character, _ = self._owner()
        sql = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "172_personal_quest_inventory.sql"
        ).read_text()
        with self.store.connection() as db:
            db.execute("DROP TABLE character_quest_items")
            for slot, quantity in ((0, 20), (1, 5)):
                db.execute(
                    "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                    "VALUES(%s,12686,%s,%s,%s)",
                    (
                        character["id"],
                        quantity,
                        character["inventory_containers"][0]["uid"],
                        slot,
                    ),
                )
            db.execute(sql)
        saved = self.reopen().character(account, character["id"])
        self.assertEqual(saved["quest_items"][0]["quantity"], 25)
        self.assertEqual(saved["inventory_items"], [])

    def test_achievement_token_reward_uses_quest_packets_with_no_bag_item(self):
        from wakfu_server.achievements.rewards import grant

        account, character, _ = self._owner()
        with self.store.connection() as db:
            packet = grant(db, self.store, character, dict(aeV=5, ckl=[12686, 20]))
        self.assertEqual(
            packet, [(13879, struct.pack(">qBih", character["id"], 0, 12686, 20))]
        )
        saved = self.reopen().character(account, character["id"])
        self.assertEqual(saved["inventory_items"], [])
        self.assertEqual(saved["quest_items"][0]["quantity"], 20)

    def test_shop_token_purchase_replay_and_publication_preserve_wallet_and_purse(self):
        from wakfu_server.shop_domain import ShopService
        from wakfu_server import shop_refresh

        account, character, generation = self._owner()
        token = self.store.issue_token(account, "api", generation=generation)
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=5000 WHERE account_id=%s", (account,)
            )
            article = db.execute(
                "INSERT INTO shop_articles(key,name,item_ref,quantity,price_kamas,category) "
                "VALUES('quest-token','Token',12686,20,1000,'items') RETURNING id"
            ).fetchone()["id"]
            for bag in character["inventory_containers"]:
                for slot in range(bag["capacity"]):
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                        "VALUES(%s,2021,1,%s,%s)",
                        (character["id"], bag["uid"], slot),
                    )
        service = ShopService(self.store)
        first = service.purchase(token, article, "quest-purchase")
        replay = ShopService(self.reopen()).purchase(token, article, "quest-purchase")
        self.assertEqual(first, replay)
        self.assertEqual(first["balance"], 4000)
        update = shop_refresh.pending(self.store, account, character)
        self.assertEqual(update["character"]["quest_items"][0]["quantity"], 20)
        self.assertEqual(sum(opcode == 13879 for opcode, _ in update["packets"]), 1)
        self.assertFalse(any(opcode == 12471 for opcode, _ in update["packets"]))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
                ).fetchone()["kamas"],
                4000,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM shop_orders WHERE account_id=%s",
                    (account,),
                ).fetchone()["n"],
                1,
            )

    def test_dungeon_quantity_criteria_read_personal_quest_and_account_artifact_separately(
        self,
    ):
        from wakfu_server.maps.dungeon_criteria import evaluate

        account, character, _ = self._owner()
        with self.store.connection() as db:
            quest_inventory.grant(db, character["id"], 12686, 20)
        saved = self.store.character(account, character["id"])
        self.assertTrue(
            evaluate(self.store, "GetItemQuantity(12686) >= 20", character=saved)
        )
        self.assertFalse(
            evaluate(self.store, "GetItemQuantity(12686) >= 21", character=saved)
        )
        self.assertTrue(
            evaluate(self.store, "GetItemQuantity(18722) == 1", character=saved)
        )
