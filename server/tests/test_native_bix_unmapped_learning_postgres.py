"""Native bIx knowledge outputs do not imply portable placement templates."""
import struct

from postgres_case import PostgresCase
from wakfu_server.items.cosmetic_learning import learn_item
from wakfu_server.items.haven_bag_furniture_catalog import resolve_item


class NativeBixUnmappedLearningPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("unmapped_bix", "password-test")["id"]
        self.character = self.store.create_character(self.account, "Native bIx Learner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])

    def add_item(self, reference, quantity=2):
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character["id"],),
            ).fetchone()["uid"]
            slot = db.execute(
                "SELECT COALESCE(MAX(slot)+1,0) AS slot FROM inventory_items WHERE container=%s",
                (bag,),
            ).fetchone()["slot"]
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s) RETURNING uid",
                (self.character["id"], reference, quantity, bag, slot),
            ).fetchone()["uid"]

    def quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
        return None if row is None else row["quantity"]

    def test_native_learning_output_without_portable_mapping_grants_once(self):
        source_ref, action_id, learned_ref, template_ref = 14316, 2475, 14316, 16529
        self.assertIsNone(resolve_item(learned_ref))
        with self.store.connection() as db:
            descriptor = db.execute(
                "SELECT item_ref,action_id,learned_refs,template_ids,has_criteria "
                "FROM native_furniture_learning_actions WHERE item_ref=%s",
                (source_ref,),
            ).fetchone()
        self.assertEqual(
            (
                descriptor["item_ref"],
                descriptor["action_id"],
                descriptor["learned_refs"],
                descriptor["template_ids"],
                descriptor["has_criteria"],
            ),
            (source_ref, action_id, [learned_ref], [template_ref], False),
        )

        source_uid = self.add_item(source_ref)
        body = struct.pack(">iq", action_id, source_uid)
        result = learn_item(
            self.store, self.account, self.generation, self.character["id"], body
        )
        self.assertTrue(result["applied"])
        self.assertEqual(self.quantity(source_uid), 1)
        self.assertEqual(
            [opcode for opcode, _ in result["packets"]], [12470, 13873, 13247]
        )
        self.assertEqual(
            result["packets"][-1][1],
            struct.pack(">I", 1) + struct.pack(">I", learned_ref) + b"\x01",
        )
        with self.store.connection() as db:
            self.assertTrue(
                db.execute(
                    "SELECT 1 FROM account_furniture_knowledge "
                    "WHERE account_id=%s AND item_ref=%s",
                    (self.account, learned_ref),
                ).fetchone()
            )
            receipt = db.execute(
                "SELECT source_ref,action_id,learned_refs FROM furniture_learning_receipts "
                "WHERE account_id=%s AND source_uid=%s",
                (self.account, source_uid),
            ).fetchone()
        self.assertEqual(
            (receipt["source_ref"], receipt["action_id"], receipt["learned_refs"]),
            (source_ref, action_id, [learned_ref]),
        )

        replay = learn_item(
            self.store, self.account, self.generation, self.character["id"], body
        )
        self.assertFalse(replay["applied"])
        self.assertEqual(self.quantity(source_uid), 1)
        self.assertEqual([opcode for opcode, _ in replay["packets"]], [13873])
        with self.reopen().connection() as db:
            self.assertTrue(
                db.execute(
                    "SELECT 1 FROM account_furniture_knowledge "
                    "WHERE account_id=%s AND item_ref=%s",
                    (self.account, learned_ref),
                ).fetchone()
            )
