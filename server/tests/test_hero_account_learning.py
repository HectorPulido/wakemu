"""Account learning consumes the active hero's UID and fences consumed retries."""
import struct

from postgres_case import PostgresCase
from wakfu_server.items import cosmetic_learning
from wakfu_server.characters import heroes
from wakfu_server.characters.cosmetic_store import load as load_cosmetics


class HeroAccountLearningTests(PostgresCase):
    def fixture(self, *, active=True):
        account = self.store.register("hero-learning", "local-password")["id"]
        main = self.store.create_character(account, "Learning Main")
        hero = self.store.create_character(account, "Learning Hero")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        if active:
            heroes.add(self.store, account, generation, main["id"], hero["id"])
        return account, generation, main, hero

    def item(self, hero, reference, slot=0):
        with self.store.connection() as db:
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,1,%s,%s) RETURNING uid",
                (hero["id"], reference, hero["inventory_containers"][0]["uid"], slot),
            ).fetchone()["uid"]

    def test_native_learning_kinds_consume_hero_share_account_and_retry_missing_uid(
        self,
    ):
        account, generation, main, hero = self.fixture()
        cases = (
            ("cosmetic", 9727, 7692, "cosmetic_learning_receipts"),
            ("title", 11431, 1619, "title_learning_receipts"),
            ("emote", 8189, 308, "emote_learning_receipts"),
            ("furniture", 6293, 466, "furniture_learning_receipts"),
        )
        for kind, reference, action, table in cases:
            with self.subTest(kind=kind):
                uid = self.item(hero, reference)
                body = struct.pack(">iq", action, uid)
                result = cosmetic_learning.learn_item(
                    self.store, account, generation, main["id"], body
                )
                self.assertTrue(result["applied"])
                self.assertEqual(result["character"]["id"], hero["id"])
                self.assertEqual(
                    self.store.character(account, hero["id"])["inventory_items"], []
                )
                repeated = cosmetic_learning.learn_item(
                    self.reopen(), account, generation, main["id"], body
                )
                self.assertFalse(repeated["applied"])
                self.assertEqual(repeated["character"]["id"], hero["id"])
                self.assertFalse(
                    any(opcode == 12470 for opcode, _ in repeated["packets"])
                )
                with self.store.connection() as db:
                    receipt = db.execute(
                        f"SELECT character_id FROM {table} WHERE account_id=%s AND source_uid=%s",
                        (account, uid),
                    ).fetchone()
                    self.assertEqual(receipt["character_id"], hero["id"])
                    self.assertEqual(
                        db.execute(
                            "SELECT character_id FROM sessions WHERE account_id=%s",
                            (account,),
                        ).fetchone()["character_id"],
                        main["id"],
                    )
                with self.assertRaises(ValueError):
                    cosmetic_learning.learn_item(
                        self.store,
                        account,
                        generation,
                        main["id"],
                        struct.pack(">iq", action + 1, uid),
                    )
        with self.reopen().connection() as db:
            self.assertIn((3, 9727, 0, 0), load_cosmetics(db, account).items)
            self.assertIn((7, 137, 0, 0), load_cosmetics(db, account).items)
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM account_emote_knowledge WHERE account_id=%s AND emote_id=20001",
                    (account,),
                ).fetchone()
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM account_furniture_knowledge WHERE account_id=%s AND item_ref=6293",
                    (account,),
                ).fetchone()
            )
        self.assertEqual(
            self.store.character(account, main["id"])["inventory_items"], []
        )

    def test_inactive_hero_source_and_consumed_receipt_are_rejected(self):
        account, generation, main, hero = self.fixture(active=False)
        uid = self.item(hero, 9727)
        body = struct.pack(">iq", 7692, uid)
        with self.assertRaises(ValueError):
            cosmetic_learning.learn_item(
                self.store, account, generation, main["id"], body
            )
        self.assertEqual(
            self.store.character(account, hero["id"])["inventory_items"][0]["quantity"],
            1,
        )
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        cosmetic_learning.learn_item(self.store, account, generation, main["id"], body)
        heroes.remove(self.store, account, generation, main["id"], hero["id"])
        with self.assertRaises(ValueError):
            cosmetic_learning.learn_item(
                self.store, account, generation, main["id"], body
            )

    def test_foreign_account_cannot_use_source_or_replay_account_receipt(self):
        account, generation, main, hero = self.fixture()
        uid = self.item(hero, 9727)
        other_account = self.store.register("foreign-learning", "local-password")["id"]
        other = self.store.create_character(other_account, "Foreign Learner")
        other_generation = self.store.begin_session(other_account)
        self.store.select_character(other_account, other_generation, other["id"])
        body = struct.pack(">iq", 7692, uid)
        for consumed in (False, True):
            if consumed:
                cosmetic_learning.learn_item(
                    self.store, account, generation, main["id"], body
                )
            with self.subTest(consumed=consumed), self.assertRaises(ValueError):
                cosmetic_learning.learn_item(
                    self.store, other_account, other_generation, other["id"], body
                )
        with self.store.connection() as db:
            self.assertEqual(load_cosmetics(db, other_account).items, ())
