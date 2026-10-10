"""Account emote access, learning and native occupation behavior in PostgreSQL."""
import struct
import time
import unittest

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.characters import emotes
from wakfu_server.items import cosmetic_learning as item_learning


class NativeEmotePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("emote-account", "emote-password")["id"]
        self.character = self.store.create_character(self.account, "Emote Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.other_character = self.store.create_character(self.account, "Emote Alt")
        self.foreign_account = self.store.register("emote-foreign", "emote-password")[
            "id"
        ]
        self.foreign = self.store.create_character(
            self.foreign_account, "Foreign Owner"
        )
        self.item_uid = self._insert_item(self.character["id"], 8189, 2)
        self.foreign_uid = self._insert_item(self.foreign["id"], 8189, 1)

    def _insert_item(self, character_id, reference, quantity):
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

    def _learn(self, uid, action=308):
        return item_learning.learn_item(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", action, uid),
        )

    def _quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
        return None if row is None else row["quantity"]

    def test_unlock_all_flag_and_learned_only_views_are_account_scoped(self):
        with self.store.connection() as db:
            default_ids = emotes.allowed_ids(db, self.account)
            self.assertIn(20001, default_ids)
            db.execute(
                "UPDATE settings SET value=%s WHERE name='emote_policy'",
                (Jsonb({"unlock_all": False}),),
            )
            self.assertEqual((), emotes.allowed_ids(db, self.account))
        learned = self._learn(self.item_uid)
        self.assertTrue(learned["applied"])
        self.assertIn((12266, struct.pack(">iB", 20001, 1)), learned["packets"])
        with self.store.connection() as db:
            self.assertEqual((20001,), emotes.allowed_ids(db, self.account))
            self.assertEqual((), emotes.allowed_ids(db, self.foreign_account))
            db.execute(
                "UPDATE settings SET value=%s WHERE name='emote_policy'",
                (Jsonb({"unlock_all": True}),),
            )
            unlocked = emotes.allowed_ids(db, self.account)
            self.assertGreater(len(unlocked), 1)
            db.execute(
                "UPDATE settings SET value=%s WHERE name='emote_policy'",
                (Jsonb({"unlock_all": False}),),
            )
            self.assertEqual((20001,), emotes.allowed_ids(db, self.account))

    def test_account_learning_consumes_once_replays_once_and_survives_reopen(self):
        first = self._learn(self.item_uid)
        replay = self._learn(self.item_uid)
        self.assertTrue(first["applied"])
        self.assertFalse(replay["applied"])
        self.assertEqual(1, self._quantity(self.item_uid))
        with self.reopen().connection() as db:
            self.assertIn(20001, emotes.allowed_ids(db, self.account))
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM emote_learning_receipts WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["n"],
            )
        next_generation = self.store.begin_session(self.account)
        self.store.select_character(
            self.account, next_generation, self.other_character["id"]
        )
        with self.store.connection() as db:
            self.assertIn(20001, emotes.allowed_ids(db, self.account))

    def test_invalid_action_malformed_foreign_and_duplicate_requests_do_not_consume(
        self,
    ):
        with self.assertRaises(ValueError):
            self._learn(self.item_uid, action=999999)
        with self.assertRaises(ValueError):
            item_learning.learn_item(
                self.store, self.account, self.generation, self.character["id"], b"bad"
            )
        with self.assertRaises(ValueError):
            item_learning.learn_item(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">iq", 308, self.foreign_uid),
            )
        self.assertEqual(2, self._quantity(self.item_uid))
        self.assertEqual(1, self._quantity(self.foreign_uid))
        self._learn(self.item_uid)
        duplicate_uid = self._insert_item(self.character["id"], 8189, 1)
        with self.assertRaisesRegex(ValueError, "already learned"):
            self._learn(duplicate_uid)
        self.assertEqual(1, self._quantity(duplicate_uid))

    def test_native_untargeted_and_targeted_play_checks_scope_and_combat(self):
        character = {
            "id": self.character["id"],
            "map_id": 527,
            "instance_id": 0,
            "x": 1,
            "y": 2,
            "z": 0,
            "hp": 100,
        }
        allowed = emotes.prepare_play(
            self.store,
            self.account,
            self.generation,
            character,
            struct.pack(">iq", 20001, -1),
            resolve_target=lambda _id: None,
            in_fight=lambda _id: False,
        )
        self.assertEqual(12088, allowed["packet"][0])
        self.assertEqual(1800, allowed["duration_ms"])
        with self.assertRaisesRegex(ValueError, "cannot specify a target"):
            emotes.prepare_play(
                self.store,
                self.account,
                self.generation,
                character,
                struct.pack(">iq", 20001, 999),
                resolve_target=lambda _id: None,
                in_fight=lambda _id: False,
            )
        with self.assertRaisesRegex(ValueError, "combat"):
            emotes.prepare_play(
                self.store,
                self.account,
                self.generation,
                character,
                struct.pack(">iq", 20001, -1),
                resolve_target=lambda _id: None,
                in_fight=lambda _id: True,
            )
        target_id = 20069
        target = {"id": 999, "map_id": 527, "instance_id": 0, "hp": 100}
        targeted = emotes.prepare_play(
            self.store,
            self.account,
            self.generation,
            character,
            struct.pack(">iq", target_id, target["id"]),
            resolve_target=lambda _id: target,
            in_fight=lambda _id: False,
        )
        self.assertEqual(1300, targeted["duration_ms"])
        self.assertIn(b"targetId", targeted["packet"][1])
        target["map_id"] = 999
        with self.assertRaisesRegex(ValueError, "target is unavailable"):
            emotes.prepare_play(
                self.store,
                self.account,
                self.generation,
                character,
                struct.pack(">iq", target_id, target["id"]),
                resolve_target=lambda _id: target,
                in_fight=lambda _id: False,
            )

    def test_target_instance_combat_occupancy_active_emote_and_stale_lease_rejected(
        self,
    ):
        character = {
            "id": self.character["id"],
            "map_id": 527,
            "instance_id": 0,
            "mount_state": {"mounted": False},
            "hp": 100,
        }
        request = struct.pack(">iq", 20069, 999)
        target = {"id": 999, "map_id": 527, "instance_id": 0, "hp": 100}
        for changed, message in (
            ({"map_id": 528}, "target is unavailable"),
            ({"instance_id": 7}, "target is unavailable"),
        ):
            invalid = dict(target, **changed)
            with self.subTest(changed=changed), self.assertRaisesRegex(
                ValueError, message
            ):
                emotes.prepare_play(
                    self.store,
                    self.account,
                    self.generation,
                    character,
                    request,
                    resolve_target=lambda _id, value=invalid: value,
                    in_fight=lambda _id: False,
                )
        with self.assertRaisesRegex(ValueError, "target is unavailable"):
            emotes.prepare_play(
                self.store,
                self.account,
                self.generation,
                character,
                request,
                resolve_target=lambda _id: target,
                in_fight=lambda actor_id: actor_id == target["id"],
            )
        with self.assertRaisesRegex(ValueError, "target is unavailable"):
            emotes.prepare_play(
                self.store,
                self.account,
                self.generation,
                character,
                request,
                resolve_target=lambda _id: target,
                in_fight=lambda _id: False,
                occupied=lambda actor_id: actor_id == target["id"],
            )
        with self.assertRaisesRegex(ValueError, "combat"):
            emotes.prepare_play(
                self.store,
                self.account,
                self.generation,
                character,
                struct.pack(">iq", 20001, -1),
                resolve_target=lambda _id: None,
                in_fight=lambda _id: False,
                occupied=lambda _id: True,
            )
        occupied_character = dict(character, _emote_until=time.monotonic() + 30)
        with self.assertRaisesRegex(ValueError, "active occupation"):
            emotes.prepare_play(
                self.store,
                self.account,
                self.generation,
                occupied_character,
                request,
                resolve_target=lambda _id: target,
                in_fight=lambda _id: False,
            )
        self.store.end_session(self.account, self.generation)
        with self.assertRaises(ValueError):
            emotes.prepare_play(
                self.store,
                self.account,
                self.generation,
                character,
                struct.pack(">iq", 20001, -1),
                resolve_target=lambda _id: None,
                in_fight=lambda _id: False,
            )


if __name__ == "__main__":
    unittest.main()
