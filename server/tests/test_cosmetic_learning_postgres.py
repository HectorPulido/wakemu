"""Real transactional account learning for native bIt item actions."""
import struct
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server import cosmetic_learning as learning
from wakfu_server.characters.cosmetic_store import load
from wakfu_server.wire import proto_fields


class CosmeticLearningTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("cosmetic_test", "password-test")["id"]
        self.character = self.store.create_character(self.account, "Cosmetic Test")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character["id"],),
            ).fetchone()["uid"]
            db.execute("DELETE FROM inventory_items WHERE container=%s", (bag,))
            self.guard = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,9727,2,%s,0) RETURNING uid",
                (self.character["id"], bag),
            ).fetchone()["uid"]
            self.ninja = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,12202,1,%s,1) RETURNING uid",
                (self.character["id"], bag),
            ).fetchone()["uid"]

    def learn(self, uid, action):
        return learning.learn_item(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", action, uid),
        )

    def quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
            return row["quantity"] if row else 0

    def test_both_source_items_learn_account_costumes_and_consume_once(self):
        self.assertTrue(self.learn(self.guard, 7692)["applied"])
        self.assertTrue(self.learn(self.ninja, 5716)["applied"])
        self.assertFalse(self.learn(self.guard, 7692)["applied"])
        self.assertFalse(self.learn(self.ninja, 5716)["applied"])
        self.assertEqual((self.quantity(self.guard), self.quantity(self.ninja)), (1, 0))
        with self.reopen().connection() as db:
            record = load(db, self.account)
        self.assertEqual(set(record.items), {(3, 9727, 0, 0), (3, 12202, 0, 0)})
        self.assertIn(self.character["id"], dict(record.selections))

    def test_wrong_action_and_expired_session_do_not_consume(self):
        with self.assertRaises(ValueError):
            self.learn(self.guard, 5716)
        self.store.end_session(self.account, self.generation)
        with self.assertRaises(ValueError):
            self.learn(self.guard, 7692)
        self.assertEqual(self.quantity(self.guard), 2)

    def test_duplicate_owned_new_item_is_not_consumed(self):
        self.learn(self.guard, 7692)
        with self.store.connection() as db:
            uid = db.execute(
                "UPDATE inventory_items SET reference=9727 WHERE uid=%s RETURNING uid",
                (self.ninja,),
            ).fetchone()["uid"]
        with self.assertRaisesRegex(ValueError, "already learned"):
            self.learn(uid, 7692)
        self.assertEqual(self.quantity(uid), 1)

    def test_learning_another_item_preserves_existing_aura_and_sprint(self):
        from psycopg.types.json import Jsonb
        from wakfu_server.characters.cosmetics import OwnedCosmetics

        record = OwnedCosmetics(self.account, ((4, 20820, 0, 0), (6, 18299, 0, 0)))
        record = record.equip_single(self.character, 4, 20820).equip_single(
            self.character, 6, 18299
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_cosmetics(account_id,record) VALUES(%s,%s)",
                (self.account, Jsonb(record.to_record())),
            )
        self.learn(self.guard, 7692)
        with self.reopen().connection() as db:
            saved = load(db, self.account)
        self.assertEqual(saved.selected_single(self.character["id"], 4), 20820)
        self.assertEqual(saved.selected_single(self.character["id"], 6), 18299)

    def test_foreign_character_item_cannot_be_learned(self):
        other = self.store.create_character(self.account, "Other Cosmetic")
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (other["id"],),
            ).fetchone()["uid"]
            db.execute("DELETE FROM inventory_items WHERE container=%s", (bag,))
            uid = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,9727,1,%s,0) RETURNING uid",
                (other["id"], bag),
            ).fetchone()["uid"]
        with self.assertRaises(ValueError):
            self.learn(uid, 7692)
        self.assertEqual(self.quantity(uid), 1)

    def test_receipt_failure_rolls_back_ownership_and_consumption(self):
        with patch.object(
            learning, "snapshot", side_effect=RuntimeError("forced rollback")
        ):
            with self.assertRaisesRegex(RuntimeError, "forced rollback"):
                self.learn(self.guard, 7692)
        self.assertEqual(self.quantity(self.guard), 2)
        with self.store.connection() as db:
            self.assertEqual(load(db, self.account).items, ())
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM cosmetic_learning_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_title_scroll_learns_native_title_id_account_wide_and_consumes_once(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET reference=11431 WHERE uid=%s", (self.guard,)
            )
        self.assertTrue(self.learn(self.guard, 1619)["applied"])
        self.assertFalse(self.learn(self.guard, 1619)["applied"])
        self.assertEqual(self.quantity(self.guard), 1)
        with self.reopen().connection() as db:
            owned = load(db, self.account)
        self.assertIn((7, 137, 0, 0), owned.items)
        self.assertNotIn((7, 11431, 0, 0), owned.items)
        category = next(
            value
            for tag, value in proto_fields(owned.inventory_component()[4:])
            if tag == 10 and dict(proto_fields(value))[8] == 7
        )
        published = list(proto_fields(dict(proto_fields(category))[18]))
        self.assertEqual([tag for tag, _ in published], [10])
        self.assertEqual(dict(proto_fields(published[0][1]))[8], 137)

    def test_wrong_title_action_does_not_consume_and_bound_title_is_learnable(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET reference=11431 WHERE uid=%s", (self.guard,)
            )
        with self.assertRaises(ValueError):
            self.learn(self.guard, 99999)
        self.assertEqual(self.quantity(self.guard), 2)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET reference=14199 WHERE uid=%s", (self.guard,)
            )
        self.assertTrue(self.learn(self.guard, 12302)["applied"])
        self.assertEqual(self.quantity(self.guard), 1)
        with self.store.connection() as db:
            self.assertIn((7, 656, 0, 0), load(db, self.account).items)

    def test_title_receipt_failure_rolls_back_account_knowledge_and_consumption(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET reference=11431 WHERE uid=%s", (self.guard,)
            )
        with patch.object(
            learning, "snapshot", side_effect=RuntimeError("forced rollback")
        ):
            with self.assertRaisesRegex(RuntimeError, "forced rollback"):
                self.learn(self.guard, 1619)
        self.assertEqual(self.quantity(self.guard), 2)
        with self.store.connection() as db:
            self.assertEqual(load(db, self.account).items, ())
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM title_learning_receipts"
                ).fetchone()["n"],
                0,
            )

    def test_another_character_can_select_account_owned_title_after_login(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET reference=11431 WHERE uid=%s", (self.guard,)
            )
        self.learn(self.guard, 1619)
        other = self.store.create_character(self.account, "Title Alt")
        other = self.store.select_character(self.account, self.generation, other["id"])
        from wakfu_server.characters.cosmetics import OwnedCosmetics

        record = OwnedCosmetics.from_record(
            other["owned_cosmetics"], account_id=self.account
        )
        preset = next(
            index
            for index, row in enumerate(record.selections, 1)
            if row[0] == other["id"]
        )
        from wakfu_server.wire import proto_field

        selected = self.store.equip_owned_finishers(
            self.account,
            other["id"],
            13765,
            struct.pack(">iiBB", preset, 7, 1, 1) + proto_field(8, 137),
        )
        self.assertEqual(
            OwnedCosmetics.from_record(
                selected["owned_cosmetics"], account_id=self.account
            ).selected_single(other["id"], 7),
            137,
        )
