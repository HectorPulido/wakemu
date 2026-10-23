"""Native single-use emote items consume only after occupation validation."""
import struct
import unittest

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.emote_item_actions import action_class, play


class EmoteItemActionsPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("emote-item-test", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Emote Item")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.item_uid = self._give(self.character["id"], 19023, 2)

    def _give(self, character_id, reference, quantity):
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

    def _body(self, action=7138, uid=None, target=-1):
        return struct.pack(
            ">iqq", action, self.item_uid if uid is None else uid, target
        )

    def _give(self, character_id, reference, quantity):
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

    def _quantity(self, uid=None):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s",
                (self.item_uid if uid is None else uid,),
            ).fetchone()
        return None if row is None else row["quantity"]

    def _play(self, body=None, **kwargs):
        character = dict(self.store.character(self.account, self.character["id"]))
        character.update(map_id=527, instance_id=0, x=1, y=2, z=0, hp=100)
        options = {
            "resolve_target": lambda _target_id: None,
            "in_fight": lambda _actor_id: False,
        }
        options.update(kwargs)
        return play(
            self.store,
            self.account,
            self.generation,
            character,
            self._body() if body is None else body,
            **options,
        )

    def test_use_consumes_one_and_prepares_the_native_occupation_without_learning(self):
        self.assertEqual("bHY", action_class(self._body()))
        result = self._play()
        self.assertTrue(result["applied"])
        self.assertEqual(1, self._quantity())
        self.assertEqual(12088, result["packet"][0])
        self.assertEqual(
            (12470, struct.pack(">qh", self.item_uid, -1)), result["packets"][0]
        )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM account_emote_knowledge WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["n"],
            )

    def test_invalid_context_action_and_target_leave_source_untouched(self):
        with self.assertRaisesRegex(ValueError, "combat"):
            self._play(in_fight=lambda _actor_id: True)
        with self.assertRaises(ValueError):
            self._play(self._body(action=999999))
        with self.assertRaises(ValueError):
            self._play(self._body()[:-1])
        with self.assertRaisesRegex(ValueError, "cannot specify a target"):
            self._play(self._body(target=123))
        self.assertEqual(2, self._quantity())

    def test_unsupported_emote_definition_does_not_consume_source(self):
        with self.store.connection() as db:
            db.execute("DELETE FROM native_emote_definitions WHERE emote_id=20146")
        with self.assertRaisesRegex(ValueError, "definition is unavailable"):
            self._play()
        self.assertEqual(2, self._quantity())

    def test_targeted_emote_checks_live_target_scope_fight_and_occupation(self):
        target_character = self.store.create_character(self.account, "Emote Target")
        source_uid = self._give(self.character["id"], 19595, 2)
        target = dict(
            id=target_character["id"],
            map_id=527,
            instance_id=0,
            hp=100,
            _emote_until=0,
        )
        actor_id = self.character["id"]
        body = self._body(action=7447, uid=source_uid, target=target["id"])

        with self.assertRaisesRegex(ValueError, "target is unavailable"):
            self._play(body, resolve_target=lambda _id: dict(target, map_id=528))
        with self.assertRaisesRegex(ValueError, "target is unavailable"):
            self._play(
                body,
                resolve_target=lambda _id: target,
                in_fight=lambda actor: actor == target["id"],
            )
        with self.assertRaisesRegex(ValueError, "target is unavailable"):
            self._play(
                body,
                resolve_target=lambda _id: target,
                occupied=lambda actor: actor == target["id"],
            )
        self.assertEqual(2, self._quantity(source_uid))

        result = self._play(body, resolve_target=lambda _id: target)
        self.assertEqual(1, self._quantity(source_uid))
        self.assertEqual(12088, result["packet"][0])
        self.assertIn(b"targetId", result["packet"][1])

    def test_native_use_criteria_block_battleground_and_durable_state_without_consuming(
        self,
    ):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1161 WHERE id=%s", (self.character["id"],)
            )
        with self.assertRaisesRegex(ValueError, "criterion"):
            self._play()
        self.assertEqual(2, self._quantity())

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527 WHERE id=%s", (self.character["id"],)
            )
            db.execute(
                "INSERT INTO character_consumable_buffs(character_id,state_id,level,"
                "source_item_ref,source_item_uid,clock,duration_ms,remaining_ms,metadata) "
                "VALUES(%s,4878,1,19023,%s,'event',0,0,%s)",
                (
                    self.character["id"],
                    self.item_uid,
                    Jsonb({"metadata": {}, "removal_event_ids": [1030]}),
                ),
            )
        with self.assertRaisesRegex(ValueError, "criterion"):
            self._play()
        self.assertEqual(2, self._quantity())


if __name__ == "__main__":
    unittest.main()
