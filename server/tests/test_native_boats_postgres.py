"""Owned SQL source authority for native boats, in an isolated schema."""
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import native_boats


class NativeBoatAuthorityTests(PostgresCase):
    def setUp(self):
        super().setUp()
        with self.store.connection() as db:
            document = native_boats.load(db)
        endpoints = {row["id"]: row for row in document["endpoints"]}
        links = {}
        for row in document["routes"]:
            links.setdefault(frozenset((row["source"], row["destination"])), []).append(
                row
            )
        indexes = patch.object(
            native_boats, "_indexes", return_value=(endpoints, links)
        )
        indexes.start()
        self.addCleanup(indexes.stop)
        self.store.clock = lambda: 1000.0
        self.account = self.store.register("boat-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Boat Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=504,instance_id=0,x=4,y=3,z=9,level=50 WHERE id=%s",
                (self.character["id"],),
            )
        self.character = self.store.character(self.account, self.character["id"])
        self.body = struct.pack(">qq", 18259, 21678)
        self.origin = native_boats.source(self.character, self.body)

    def admit(self, **overrides):
        return native_boats.admit_source(
            self.store,
            overrides.get("account_id", self.account),
            overrides.get("generation", self.generation),
            overrides.get("character", self.character),
            overrides.get("origin", self.origin),
            blocked=overrides.get("blocked", False),
        )

    def test_owned_selected_actor_and_exact_source_are_authorized(self):
        self.assertTrue(self.admit())
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT map_id,instance_id,x,y,z,level FROM characters WHERE id=%s",
                (self.character["id"],),
            ).fetchone()
        self.assertEqual((504, 0, 4, 3, 9, 50), tuple(saved.values()))

    def test_stale_generation_wrong_owner_and_changed_selected_actor_rejected(self):
        with self.assertRaises(ValueError):
            self.admit(generation="invalid-generation")
        other = self.store.register("boat-other", "local-password")["id"]
        with self.assertRaises(ValueError):
            self.admit(account_id=other)
        replacement = self.store.create_character(self.account, "Boat Replacement")
        self.store.select_character(self.account, self.generation, replacement["id"])
        with self.assertRaises(ValueError):
            self.admit()

    def test_sql_position_or_level_change_rejects_stale_live_actor(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=x+1 WHERE id=%s", (self.character["id"],)
            )
        with self.assertRaisesRegex(ValueError, "desynchronized"):
            self.admit()
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=4,level=51 WHERE id=%s",
                (self.character["id"],),
            )
        with self.assertRaisesRegex(ValueError, "desynchronized"):
            self.admit()

    def test_occupation_and_durable_combat_rejected(self):
        with self.assertRaisesRegex(ValueError, "occupation"):
            self.admit(blocked=True)
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, self.character["id"], self.account),
            )
        with self.assertRaisesRegex(ValueError, "combat"):
            self.admit()

    def test_out_of_range_private_and_tampered_source_are_rejected(self):
        for actor in (
            dict(self.character, x=9),
            dict(self.character, z=11),
            dict(self.character, instance_id=7),
            dict(self.character, x=float("nan")),
        ):
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                self.admit(character=actor)
        with self.assertRaisesRegex(ValueError, "installed native"):
            self.admit(origin=dict(self.origin, source_position=dict(x=4, y=3, z=0)))


if __name__ == "__main__":
    unittest.main()
