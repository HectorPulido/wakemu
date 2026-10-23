"""PostgreSQL coverage for repeated recustomization units on one source UID."""
import struct

from postgres_case import PostgresCase
from wakfu_server.character_recustomization import complete, request


class RecustomizationStackPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("recustom-stack", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Stack Owner")
        self.generation = self.store.begin_session(self.account)
        self.character_id = self.character["id"]
        self.store.select_character(self.account, self.generation, self.character_id)

    def _source(self):
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.character_id,),
            ).fetchone()["uid"]
            slot = db.execute(
                "SELECT COALESCE(MAX(slot)+1,0) AS slot FROM inventory_items WHERE container=%s",
                (bag,),
            ).fetchone()["slot"]
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,18292,2,%s,%s) RETURNING uid",
                (self.character_id, bag, slot),
            ).fetchone()["uid"]

    def _leave_world(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET character_id=NULL WHERE account_id=%s AND generation=%s",
                (self.account, self.generation),
            )

    def _complete(self):
        character = self.store.character(self.account, self.character_id)
        return complete(
            self.store,
            self.account,
            self.generation,
            {
                "character_id": self.character_id,
                "creation_flag": False,
                "breed_id": character["breed"],
                "character_name": character["name"],
                "appearance": {"faceIndex": 1},
            },
        )

    def test_same_uid_second_stack_unit_creates_second_completed_entitlement(self):
        source = self._source()
        body = struct.pack(">iq", 5556, source)

        # The new item-action occupation guard must roll back an actual exchange.
        from wakfu_server import player_exchanges

        other_account = self.store.register("recustom-stack-peer", "local-password")[
            "id"
        ]
        other = self.store.create_character(other_account, "Stack Peer")
        other_generation = self.store.begin_session(other_account)
        self.store.select_character(other_account, other_generation, other["id"])
        exchange = player_exchanges.invite(
            self.store, self.account, self.generation, self.character_id, other["id"]
        )
        player_exchanges.answer(
            self.store,
            other_account,
            other_generation,
            other["id"],
            exchange["id"],
            True,
        )
        with self.assertRaises(ValueError):
            request(self.store, self.account, self.generation, self.character_id, body)
        self.assertEqual(2, self._quantity(source))
        self.assertIsNone(
            self.store.character(self.account, self.character_id)["recustomization"]
        )
        player_exchanges.cancel(
            self.store, self.account, self.generation, self.character_id, exchange["id"]
        )

        first = request(
            self.store, self.account, self.generation, self.character_id, body
        )
        self.assertTrue(first["applied"])
        pending_replay = request(
            self.store, self.account, self.generation, self.character_id, body
        )
        self.assertFalse(pending_replay["applied"])
        self.assertEqual(1, self._quantity(source))
        self.assertEqual(
            first["pending"]["source_uid"], pending_replay["pending"]["source_uid"]
        )
        with self.assertRaises(ValueError):
            request(
                self.store,
                self.account,
                f"{self.generation}-stale",
                self.character_id,
                body,
            )
        self.assertEqual(1, self._quantity(source))
        self.assertEqual(
            13,
            self.store.character(self.account, self.character_id)["recustomization"][
                "mode"
            ],
        )
        self._leave_world()
        self._complete()
        self.assertEqual(1, self._quantity(source))

        self.store.select_character(self.account, self.generation, self.character_id)
        second = request(
            self.store, self.account, self.generation, self.character_id, body
        )
        self.assertTrue(
            second["applied"], "remaining stack unit must fund a new receipt"
        )
        self.assertIsNone(self._quantity(source))
        self.assertEqual(13, second["pending"]["mode"])

        self._leave_world()
        self._complete()
        with self.store.connection() as db:
            receipts = db.execute(
                "SELECT source_uid,completed_at FROM character_recustomization_receipts "
                "WHERE account_id=%s AND character_id=%s ORDER BY requested_at,source_uid",
                (self.account, self.character_id),
            ).fetchall()
        self.assertEqual(2, len(receipts))
        self.assertEqual([source, source], [row["source_uid"] for row in receipts])
        self.assertTrue(all(row["completed_at"] is not None for row in receipts))
        self.store.select_character(self.account, self.generation, self.character_id)
        with self.assertRaises(ValueError):
            request(self.store, self.account, self.generation, self.character_id, body)
        with self.store.connection() as db:
            lease = db.execute(
                "SELECT character_id FROM sessions WHERE account_id=%s", (self.account,)
            ).fetchone()
        self.assertEqual(self.character_id, lease["character_id"])

    def _quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
        return None if row is None else row["quantity"]
