"""Transactional PostgreSQL tests for native bIv Haven Bag view books."""
import struct

from postgres_case import PostgresCase
from wakfu_server.characters.cosmetic_store import load
from wakfu_server import haven_bag_view_learning as learning
from wakfu_server.wire import proto_field


class HavenBagViewLearningPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("bag_view_learning", "password-test")["id"]
        self.character = self.store.create_character(self.account, "Bag View Learner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])

    def add_item(self, reference=11426, *, quantity=1, character_id=None):
        character_id = character_id or self.character["id"]
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (character_id,),
            ).fetchone()["uid"]
            slot = db.execute(
                "SELECT COALESCE(MAX(slot)+1,0) AS slot FROM inventory_items WHERE container=%s",
                (bag,),
            ).fetchone()["slot"]
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s) RETURNING uid",
                (character_id, reference, quantity, bag, slot),
            ).fetchone()["uid"]

    def learn(
        self, uid, action=1618, *, account=None, generation=None, character_id=None
    ):
        return learning.learn(
            self.store,
            self.account if account is None else account,
            self.generation if generation is None else generation,
            self.character["id"] if character_id is None else character_id,
            struct.pack(">iq", action, uid),
        )

    def quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
        return None if row is None else row["quantity"]

    def test_all_native_biv_descriptors_match_action_catalog(self):
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT item_ref,action_id,view_id,has_criteria "
                "FROM native_bag_view_learning_actions ORDER BY item_ref"
            ).fetchall()
        self.assertEqual(len(rows), 91)
        self.assertTrue(all(row["has_criteria"] is False for row in rows))
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        native = _rules()
        for row in rows:
            item = native.get(row["item_ref"])
            self.assertIsNotNone(item, row["item_ref"])
            self.assertEqual(item.get("use_action_class"), "bIv")
            self.assertEqual(item.get("use_action_id"), row["action_id"])
            self.assertIs(item.get("use_has_criteria"), False)
            self.assertGreater(row["view_id"], 0)

        with self.store.connection() as db:
            actual = db.execute(
                "SELECT action_id,view_id,has_criteria FROM native_bag_view_learning_actions "
                "WHERE item_ref=11426"
            ).fetchone()
        self.assertEqual(
            (actual["action_id"], actual["view_id"], actual["has_criteria"]),
            (1618, 680, False),
        )

    def test_view_book_consumes_once_publishes_category_15_and_replays(self):
        uid = self.add_item(quantity=1)
        with self.store.connection() as db:
            before = load(db, self.account)
        result = self.learn(uid)
        self.assertTrue(result["applied"])
        self.assertEqual(result["packets"][0], (12470, struct.pack(">qh", uid, -1)))
        self.assertIsNone(self.quantity(uid))
        with self.store.connection() as db:
            record = load(db, self.account)
        self.assertIn((15, 680, 0, 0), record.items)
        self.assertEqual(record.selections, () if before is None else before.selections)
        self.assertEqual(
            record.inactive_characters,
            () if before is None else before.inactive_characters,
        )
        self.assertEqual(result["packets"][-1], learning.snapshot(record))

        replay = self.learn(uid)
        self.assertFalse(replay["applied"])
        self.assertEqual([packet[0] for packet in replay["packets"]], [13873])
        self.assertIsNone(self.quantity(uid))
        with self.reopen().connection() as db:
            receipt = db.execute(
                "SELECT source_ref,action_id,view_id FROM bag_view_learning_receipts "
                "WHERE account_id=%s AND source_uid=%s",
                (self.account, uid),
            ).fetchone()
            saved = load(db, self.account)
        self.assertEqual(
            (receipt["source_ref"], receipt["action_id"], receipt["view_id"]),
            (11426, 1618, 680),
        )
        self.assertIn((15, 680, 0, 0), saved.items)

    def test_duplicate_view_wrong_action_foreign_uid_and_stale_lease_are_atomic(self):
        first_uid = self.add_item()
        self.assertTrue(self.learn(first_uid)["applied"])
        duplicate_uid = self.add_item()
        with self.assertRaisesRegex(ValueError, "already learned"):
            self.learn(duplicate_uid)
        self.assertEqual(self.quantity(duplicate_uid), 1)

        wrong_uid = self.add_item(reference=11426)
        with self.assertRaises(ValueError):
            self.learn(wrong_uid, action=1619)
        self.assertEqual(self.quantity(wrong_uid), 1)

        foreign = self.store.register("bag_view_foreign", "password-test")["id"]
        other = self.store.create_character(foreign, "Foreign Bag View Owner")
        other_generation = self.store.begin_session(foreign)
        self.store.select_character(foreign, other_generation, other["id"])
        foreign_uid = self.add_item(character_id=other["id"])
        with self.assertRaises(ValueError):
            self.learn(foreign_uid)
        self.assertEqual(self.quantity(foreign_uid), 1)

        self.store.end_session(self.account, self.generation)
        with self.assertRaises(ValueError):
            self.learn(duplicate_uid)
        self.assertEqual(self.quantity(duplicate_uid), 1)

    def test_equipped_or_specific_data_source_is_not_consumed(self):
        uid = self.add_item()
        equipped = proto_field(10, proto_field(8, uid))
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_builds SET equipment=%s WHERE character_id=%s AND build_index=0",
                (equipped, self.character["id"]),
            )
        with self.assertRaisesRegex(ValueError, "Unequip"):
            self.learn(uid)
        self.assertEqual(self.quantity(uid), 1)

        with self.store.connection() as db:
            db.execute(
                "UPDATE character_builds SET equipment=%s WHERE character_id=%s AND build_index=0",
                (b"", self.character["id"]),
            )
            db.execute(
                "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) "
                "VALUES(%s,0,0)",
                (uid,),
            )
        with self.assertRaisesRegex(ValueError, "specific data"):
            self.learn(uid)
        self.assertEqual(self.quantity(uid), 1)
        with self.store.connection() as db:
            self.assertEqual(load(db, self.account).items, ())
