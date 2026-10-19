"""Native bIw knowledge may outlive a missing client emote definition."""
import struct

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import cosmetic_learning as item_learning
from wakfu_server.characters import emotes


class OpaqueEmoteLearningPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("opaque_emote", "password-test")["id"]
        self.character = self.store.create_character(self.account, "Opaque Emote")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='emote_policy'",
                (Jsonb({"unlock_all": False}),),
            )
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character["id"],),
            ).fetchone()["uid"]
            self.source_uid = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,23951,2,%s,0) RETURNING uid",
                (self.character["id"], bag),
            ).fetchone()["uid"]

    def quantity(self):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (self.source_uid,)
            ).fetchone()
        return None if row is None else row["quantity"]

    def learn(self):
        return item_learning.learn_item(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", 9934, self.source_uid),
        )

    def test_native_opaque_emote_knowledge_consumes_once_but_is_not_playable(self):
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT emote_id FROM native_emote_learning_actions WHERE item_ref=23951"
                ).fetchone()["emote_id"],
                20223,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM native_emote_definitions WHERE emote_id=20223"
                ).fetchone()
            )

        first = self.learn()
        self.assertTrue(first["applied"])
        self.assertEqual(self.quantity(), 1)
        self.assertEqual(
            first["packets"][0], (12470, struct.pack(">qh", self.source_uid, -1))
        )
        self.assertNotIn(12266, [opcode for opcode, _ in first["packets"]])
        self.assertEqual(first["packets"][-1], emotes.packet(self.store, self.account))
        with self.store.connection() as db:
            self.assertEqual(
                emotes.allowed_ids(db, self.account),
                (),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS count FROM account_emote_knowledge "
                    "WHERE account_id=%s AND emote_id=20223",
                    (self.account,),
                ).fetchone()["count"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS count FROM emote_learning_receipts "
                    "WHERE account_id=%s AND source_uid=%s",
                    (self.account, self.source_uid),
                ).fetchone()["count"],
                1,
            )

        replay = self.learn()
        self.assertFalse(replay["applied"])
        self.assertEqual(self.quantity(), 1)
        self.assertEqual([opcode for opcode, _ in replay["packets"]], [13873])
        with self.store.connection() as db:
            with self.assertRaisesRegex(ValueError, "not unlocked"):
                emotes.authorize(db, self.account, struct.pack(">iq", 20223, -1))
