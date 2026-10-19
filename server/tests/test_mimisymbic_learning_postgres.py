"""PostgreSQL tests for native bHv target-bound appearance learning."""
import json
from pathlib import Path
import struct

from postgres_case import PostgresCase
from wakfu_server import mimisymbic_learning as learning
from wakfu_server.characters.cosmetic_store import load


class MimisymbicLearningPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("mimisymbic", "password-test")["id"]
        self.character = self.store.create_character(self.account, "Mimisymbic Learner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])

    def add_item(self, reference, *, quantity=1, character_id=None):
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
        self,
        source_uid,
        target_uid,
        *,
        action=13882,
        account=None,
        generation=None,
        character_id=None
    ):
        return learning.learn(
            self.store,
            self.account if account is None else account,
            self.generation if generation is None else generation,
            self.character["id"] if character_id is None else character_id,
            struct.pack(">iqq", action, source_uid, target_uid),
        )

    def quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
        return None if row is None else row["quantity"]

    def test_all_native_targets_match_export_and_exclude_player_accessories(self):
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT target_ref,appearance_ref,category,source_sha256 "
                "FROM native_mimisymbic_targets ORDER BY target_ref,category"
            ).fetchall()
        self.assertEqual(len(rows), 7397)
        self.assertEqual({row["category"] for row in rows}, set(range(8, 15)))
        self.assertTrue(all(row["target_ref"] == row["appearance_ref"] for row in rows))
        self.assertTrue(
            all(row["source_sha256"] == learning.CLIENT_SHA256 for row in rows)
        )
        export_path = (
            Path(__file__).resolve().parents[2]
            / ".runtime/all-learnable-items-20261018/native-mimisymbic-targets.json"
        )
        if export_path.exists():
            expected = json.loads(export_path.read_text())["rows"]
            self.assertEqual(
                {
                    (row["target_ref"], row["appearance_ref"], row["category"])
                    for row in rows
                },
                {
                    (row["target_ref"], row["appearance_ref"], row["category"])
                    for row in expected
                },
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM native_mimisymbic_targets WHERE category=16"
                ).fetchone()["count"],
                0,
            )

    def test_learns_each_native_category_consumes_source_only_and_replays_bound_receipt(
        self,
    ):
        # These are original-client target descriptors spanning the allowed
        # output classes: head, boots, first weapon, and accessory slot family.
        cases = ((2026, 8), (2023, 12), (12, 13), (2057, 14))
        for target_ref, category in cases:
            with self.subTest(target_ref=target_ref, category=category):
                source_uid = self.add_item(31508, quantity=2)
                target_uid = self.add_item(target_ref, quantity=3)
                result = self.learn(source_uid, target_uid)
                self.assertTrue(result["applied"])
                self.assertEqual(self.quantity(source_uid), 1)
                self.assertEqual(self.quantity(target_uid), 3)
                self.assertEqual(
                    result["packets"][0], (12470, struct.pack(">qh", source_uid, -1))
                )
                self.assertEqual(result["packets"][-1][0], 13873)
                with self.store.connection() as db:
                    record = load(db, self.account)
                self.assertIn((category, target_ref, 0, 0), record.items)

        # Replay is idempotent even after the source's final unit disappears;
        # the receipt binds the exact target instance and never consumes it.
        source_uid = self.add_item(31508)
        # A second appearance in an already represented category is a distinct
        # native target and exercises receipt binding independently of category.
        target_uid = self.add_item(2040)
        first = self.learn(source_uid, target_uid)
        self.assertIsNone(self.quantity(source_uid))
        self.assertEqual(self.quantity(target_uid), 1)
        replay = self.learn(source_uid, target_uid)
        self.assertFalse(replay["applied"])
        self.assertEqual([opcode for opcode, _ in replay["packets"]], [13873])
        different_target = self.add_item(2023)
        with self.assertRaisesRegex(ValueError, "receipt does not match"):
            self.learn(source_uid, different_target)
        self.assertEqual(self.quantity(different_target), 1)

        with self.reopen().connection() as db:
            receipt = db.execute(
                "SELECT target_uid,target_ref,categories,appearance_ref "
                "FROM mimisymbic_learning_receipts WHERE account_id=%s AND source_uid=%s",
                (self.account, source_uid),
            ).fetchone()
            saved = load(db, self.account)
            packet = learning.snapshot(saved)
        self.assertEqual(
            (
                receipt["target_uid"],
                receipt["target_ref"],
                receipt["categories"],
                receipt["appearance_ref"],
            ),
            (target_uid, 2040, [8], 2040),
        )
        self.assertIn((8, 2040, 0, 0), saved.items)
        self.assertEqual(packet, first["packets"][-1])

    def test_foreign_target_wrong_action_and_stale_session_are_atomic(self):
        source_uid = self.add_item(31508)
        target_uid = self.add_item(2026)
        with self.assertRaises(ValueError):
            self.learn(source_uid, target_uid, action=13881)
        self.assertEqual((self.quantity(source_uid), self.quantity(target_uid)), (1, 1))

        # Original-client witness: 2292 is a root-109 ACCESSORY slot item, but
        # eSP.cb rejects that slot as PLAYER_ACCESSORY (category 16).
        accessory_source = self.add_item(31508)
        excluded_accessory = self.add_item(2292)
        with self.assertRaisesRegex(ValueError, "verified native accessory"):
            self.learn(accessory_source, excluded_accessory)
        self.assertEqual(
            (self.quantity(accessory_source), self.quantity(excluded_accessory)),
            (1, 1),
        )

        foreign = self.store.register("mimisymbic_foreign", "password-test")["id"]
        other = self.store.create_character(foreign, "Foreign Target Owner")
        foreign_generation = self.store.begin_session(foreign)
        self.store.select_character(foreign, foreign_generation, other["id"])
        foreign_target = self.add_item(2026, character_id=other["id"])
        with self.assertRaisesRegex(ValueError, "active character"):
            self.learn(source_uid, foreign_target)
        self.assertEqual(self.quantity(source_uid), 1)
        self.assertEqual(self.quantity(foreign_target), 1)

        self.store.end_session(self.account, self.generation)
        with self.assertRaises(ValueError):
            self.learn(source_uid, target_uid)
        self.assertEqual((self.quantity(source_uid), self.quantity(target_uid)), (1, 1))
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM mimisymbic_learning_receipts WHERE account_id=%s",
                    (self.account,),
                ).fetchone()
            )
