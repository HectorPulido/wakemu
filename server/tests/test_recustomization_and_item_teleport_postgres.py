"""Identity-preserving item recustomization and retryable native teleport."""
import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server.character_recustomization import complete, request
from wakfu_server.item_teleports import acknowledge, pending, plan, use


class RecustomizationAndTeleportPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("item-transition-test", "local-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Transition Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])

    def _give(self, account, character, reference, quantity=1):
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (character,),
            ).fetchone()["uid"]
            slot = db.execute(
                "SELECT COALESCE(MAX(slot)+1,0) AS slot FROM inventory_items WHERE container=%s",
                (bag,),
            ).fetchone()["slot"]
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s) RETURNING uid",
                (character, reference, quantity, bag, slot),
            ).fetchone()["uid"]

    def _quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
        return None if row is None else row["quantity"]

    def test_recustomization_keeps_identity_progress_inventory_and_build(self):
        cid = self.character["id"]
        ticket = self._give(self.account, cid, 18292, 2)
        keepsake = self._give(self.account, cid, 12127, 1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_progression SET xp=123456 WHERE character_id=%s",
                (cid,),
            )
        before = self.store.character(self.account, cid)
        initial_builds = before["builds"]
        action = struct.pack(">iq", 5556, ticket)

        first = request(self.store, self.account, self.generation, cid, action)
        replay = request(self.store, self.account, self.generation, cid, action)
        self.assertTrue(first["applied"])
        self.assertFalse(replay["applied"])
        self.assertEqual(1, self._quantity(ticket))
        self.assertEqual(13, first["pending"]["mode"])

        with self.assertRaises(ValueError):
            request(self.store, self.account, self.generation, cid, action[:-1])
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET character_id=NULL WHERE account_id=%s AND generation=%s",
                (self.account, self.generation),
            )

        identity = dict(
            character_id=cid,
            creation_flag=False,
            breed_id=before["breed"],
            character_name=before["name"],
            appearance={"faceIndex": 1},
        )
        forbidden = dict(identity, creation_flag=True)
        with self.assertRaises(ValueError):
            complete(self.store, self.account, self.generation, forbidden)
        with self.assertRaisesRegex(ValueError, "class changes"):
            complete(
                self.store,
                self.account,
                self.generation,
                dict(identity, breed_id=19 if before["breed"] != 19 else 16),
            )
        completed = complete(self.store, self.account, self.generation, identity)
        after = self.store.character(self.account, cid)
        self.assertTrue(completed["recustomized"])
        self.assertEqual(cid, after["id"])
        self.assertEqual(before["name"], after["name"])
        self.assertEqual(before["breed"], after["breed"])
        self.assertEqual(123456, after["xp"])
        self.assertEqual(initial_builds, after["builds"])
        self.assertIn(keepsake, {row["uid"] for row in after["inventory_items"]})
        self.assertEqual(1, self._quantity(ticket))
        self.assertIsNone(after["recustomization"])
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT completed_at,completion FROM character_recustomization_receipts "
                "WHERE account_id=%s AND source_uid=%s",
                (self.account, ticket),
            ).fetchone()
        self.assertIsNotNone(receipt["completed_at"])
        self.assertEqual(cid, receipt["completion"]["character_id"])

    def test_teleport_commits_relocation_once_and_acknowledges_retryably(self):
        from wakfu_server.native_world_context import is_battleground

        cid = self.character["id"]
        source = self._give(self.account, cid, 14306, 1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=552,instance_id=0,x=0,y=0,z=0 WHERE id=%s",
                (cid,),
            )
        before = self.store.character(self.account, cid)
        body = struct.pack(">iq", 2645, source)
        route = plan(2645)
        self.assertEqual(14306, route["item_ref"])
        self.assertFalse(is_battleground(before["map_id"]))

        result = use(
            self.store, None, self.account, self.generation, cid, body, in_fight=False
        )
        self.assertTrue(result["applied"])
        self.assertTrue(result["pending_delivery"])
        self.assertEqual(1, result["consumed"])
        self.assertEqual(
            route["destination"],
            {
                key: result["character"][key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            },
        )
        self.assertIsNone(self._quantity(source))

        retry = use(
            self.store, None, self.account, self.generation, cid, body, in_fight=False
        )
        self.assertFalse(retry["applied"])
        self.assertEqual(result["transition"]["token"], retry["transition"]["token"])
        recovered = pending(self.store, self.account, self.generation, cid)
        self.assertEqual(
            result["transition"]["token"], recovered["transition"]["token"]
        )
        self.assertTrue(recovered["pending_delivery"])
        self.assertTrue(
            acknowledge(
                self.store,
                self.account,
                self.generation,
                cid,
                result["transition"]["token"],
            )
        )
        self.assertTrue(
            acknowledge(
                self.store,
                self.account,
                self.generation,
                cid,
                result["transition"]["token"],
            )
        )
        self.assertIsNone(pending(self.store, self.account, self.generation, cid))
        with self.store.connection() as db:
            row = db.execute(
                "SELECT delivered_at,source_item_uid FROM item_teleport_receipts WHERE token=%s",
                (result["transition"]["token"],),
            ).fetchone()
        self.assertEqual(source, row["source_item_uid"])
        self.assertIsNotNone(row["delivered_at"])

    def test_teleport_rejects_malformed_foreign_and_combat_requests_without_consuming(
        self,
    ):
        cid = self.character["id"]
        source = self._give(self.account, cid, 14306, 1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=552,instance_id=0,x=0,y=0,z=0 WHERE id=%s",
                (cid,),
            )
        with self.assertRaises(ValueError):
            use(
                self.store,
                None,
                self.account,
                self.generation,
                cid,
                b"bad",
                in_fight=False,
            )
        with self.assertRaises(ValueError):
            use(
                self.store,
                None,
                self.account,
                self.generation,
                cid,
                struct.pack(">iq", 2645, source),
                in_fight=True,
            )
        with self.assertRaises(ValueError):
            use(
                self.store,
                None,
                self.account,
                self.generation,
                cid,
                struct.pack(">iq", 999999, source),
                in_fight=False,
            )

        other = self.store.register("teleport-other", "local-password")["id"]
        foreign_char = self.store.create_character(other, "Teleport Foreign")
        foreign_uid = self._give(other, foreign_char["id"], 14306, 1)
        with self.assertRaises(ValueError):
            use(
                self.store,
                None,
                self.account,
                self.generation,
                cid,
                struct.pack(">iq", 2645, foreign_uid),
                in_fight=False,
            )
        self.assertEqual(1, self._quantity(source))
        self.assertEqual(1, self._quantity(foreign_uid))
        self.assertEqual(552, self.store.character(self.account, cid)["map_id"])


if __name__ == "__main__":
    unittest.main()
