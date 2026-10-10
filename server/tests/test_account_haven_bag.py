"""Account Haven Bag ownership survives character changes and tombstones."""
import struct

from postgres_case import PostgresCase
from wakfu_server.haven_bag_store import load, save
from wakfu_server.haven_bag_transfer import insert, remove
from wakfu_server.inventory_items import grant


class AccountHavenBagTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("account-bag", "local-password")["id"]
        self.first = self.store.create_character(self.account, "First Bag")
        self.second = self.store.create_character(self.account, "Second Bag")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.second["id"])

    def test_second_character_shares_configuration_and_physical_gems(self):
        canonical = self.first["id"]
        self.assertEqual(self.second["haven_bag"]["owner_id"], canonical)
        container = self.second["inventory_containers"][0]["uid"]
        granted = grant(
            self.store,
            self.account,
            self.generation,
            self.second["id"],
            reference=4263,
            quantity=1,
            container=container,
            slot=0,
            allowed_references={4263},
        )
        # grant returns the inventory item in the same shape as the existing
        # transfer tests; read its authoritative UID rather than assuming IDs.
        with self.store.connection() as db:
            item = db.execute(
                "SELECT uid FROM inventory_items WHERE character_id=%s AND reference=4263",
                (self.second["id"],),
            ).fetchone()
        location = {"map_id": 9, "instance_id": canonical}
        insert(
            self.store,
            self.account,
            self.generation,
            self.second["id"],
            struct.pack(">qBB", item["uid"], 1, 0),
            location=location,
        )
        with self.store.connection() as db:
            first = load(db, self.first["id"])
            second = load(db, self.second["id"])
        self.assertEqual(first, second)
        self.assertEqual(first["rooms"][1]["primary_ref"], 4263)
        remove(
            self.store,
            self.account,
            self.generation,
            self.second["id"],
            struct.pack(">qBBB", container, 0, 1, 1),
            location=location,
        )
        with self.store.connection() as db:
            self.assertEqual(load(db, canonical)["rooms"][1]["primary_ref"], -1)

    def test_account_config_survives_canonical_character_tombstone(self):
        save(self.store, self.account, self.generation, self.second["id"], locked=True)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET deleted_at=now() WHERE id=%s",
                (self.first["id"],),
            )
        reopened = self.reopen().character(self.account, self.second["id"])
        self.assertTrue(reopened["haven_bag"]["locked"])
        self.assertEqual(reopened["haven_bag"]["owner_id"], self.first["id"])

    def test_other_account_isolated_and_foreign_instance_rejected(self):
        other_account = self.store.register("other-bag", "local-password")["id"]
        other = self.store.create_character(other_account, "Other Bag")
        save(self.store, self.account, self.generation, self.second["id"], locked=True)
        self.assertFalse(other["haven_bag"]["locked"])
        with self.assertRaises(ValueError):
            insert(
                self.store,
                self.account,
                self.generation,
                self.second["id"],
                struct.pack(">qBB", 123, 1, 0),
                location={"map_id": 9, "instance_id": other["id"]},
            )
