"""Original native action outputs may own opaque knowledge without execution."""
import struct

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import cosmetic_learning
from wakfu_server.characters import emotes
from wakfu_server.wire import proto_fields


class OpaqueEmoteLearningTests(PostgresCase):
    def fixture(self, reference):
        account = self.store.register("opaque-emote", "local-password")["id"]
        character = self.store.create_character(account, "Opaque Emote")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='emote_policy'",
                (Jsonb(dict(unlock_all=False)),),
            )
            uid = db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,2,%s,0) RETURNING uid",
                (
                    character["id"],
                    reference,
                    character["inventory_containers"][0]["uid"],
                ),
            ).fetchone()["uid"]
        return account, generation, character, uid

    def snapshot_ids(self, packets):
        body = next(body for opcode, body in packets if opcode == 13873)
        self.assertEqual(struct.unpack(">II", body[:8]), (1, 10))
        self.assertEqual(struct.unpack_from(">I", body, 8)[0], len(body) - 12)
        return {
            dict(proto_fields(value))[8]
            for tag, value in proto_fields(body[12:])
            if tag == 10
        }

    def test_opaque_native_action_consumes_once_snapshots_and_never_grants_execution(
        self,
    ):
        account, generation, character, uid = self.fixture(23951)
        body = struct.pack(">iq", 9934, uid)
        result = cosmetic_learning.learn_item(
            self.store,
            account,
            generation,
            character["id"],
            body,
        )
        self.assertTrue(result["applied"])
        self.assertEqual([opcode for opcode, _ in result["packets"]], [12470, 13873])
        self.assertIn(20223, self.snapshot_ids(result["packets"]))
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM native_emote_definitions WHERE emote_id=20223"
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
                ).fetchone()["quantity"],
                1,
            )
            self.assertNotIn(20223, emotes.allowed_ids(db, account))
            with self.assertRaisesRegex(ValueError, "not unlocked"):
                emotes.authorize(db, account, struct.pack(">iq", 20223, -1))
            # Unattested positive IDs cannot enter published opaque knowledge.
            db.execute(
                "INSERT INTO account_emote_knowledge(account_id,emote_id) VALUES(%s,2147483647)",
                (account,),
            )
            self.assertNotIn(
                2147483647, self.snapshot_ids([emotes.snapshot(db, account)])
            )
        replay = cosmetic_learning.learn_item(
            self.reopen(),
            account,
            generation,
            character["id"],
            body,
        )
        self.assertFalse(replay["applied"])
        self.assertEqual([opcode for opcode, _ in replay["packets"]], [13873])
        self.assertIn(20223, self.snapshot_ids(replay["packets"]))

    def test_defined_native_emote_keeps_incremental_and_executable_knowledge(self):
        account, generation, character, uid = self.fixture(8189)
        result = cosmetic_learning.learn_item(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">iq", 308, uid),
        )
        self.assertEqual(
            [opcode for opcode, _ in result["packets"]], [12470, 12266, 13873]
        )
        self.assertIn(20001, self.snapshot_ids(result["packets"]))
        with self.store.connection() as db:
            self.assertEqual(
                emotes.authorize(db, account, struct.pack(">iq", 20001, -1)),
                (20001, -1),
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
