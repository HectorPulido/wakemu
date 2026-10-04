import struct
import tempfile
import unittest
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server.inventory_uids import reserve, initialize_pool, replenish
from wakfu_server.inventory_items import grant


class UidReservationTests(unittest.TestCase):
    def test_reservations_share_allocator_with_grants_and_enforce_current_lease(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "world.sqlite3")
            account = store.register("uid-owner", "local-password")["id"]
            char = store.create_character(account, "UID Owner")
            generation = store.begin_session(account)
            with self.assertRaises(ValueError):
                reserve(store, account, generation, char["id"], count=2)
            store.select_character(account, generation, char["id"])
            pool = reserve(store, account, generation, char["id"], count=2)
            self.assertEqual(pool["packet"][0], 13778)
            self.assertEqual(pool["packet"][1][:2], b"\x01\x02")
            item = grant(
                store,
                account,
                generation,
                char["id"],
                reference=2021,
                quantity=1,
                container=char["inventory_containers"][0]["uid"],
                slot=0,
                allowed_references={2021},
            )
            self.assertNotIn(item["uid"], pool["uids"])
            self.assertGreater(item["uid"], max(pool["uids"]))
            next_pool = reserve(
                Store(store.path), account, generation, char["id"], count=1
            )
            self.assertGreater(next_pool["uids"][0], item["uid"])
            with self.assertRaises(ValueError):
                reserve(store, account, generation, char["id"], count=127)
            store.begin_session(account)
            with self.assertRaises(ValueError):
                reserve(store, account, generation, char["id"], count=1)

    def test_reselection_replaces_unused_pool_preserves_consumed_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "world.sqlite3")
            account = store.register("pool-reset", "local-password")["id"]
            char = store.create_character(account, "Pool Reset")
            generation = store.begin_session(account)
            store.select_character(account, generation, char["id"])
            old = initialize_pool(store, account, generation, char["id"])
            consumed = old["uids"][0]
            with store.connection() as db:
                db.execute(
                    "UPDATE inventory_reserved_uids SET used_request=? WHERE uid=?",
                    (b"consumed-request", consumed),
                )
            all_uids = set(old["uids"])
            for _ in range(6):
                pool = initialize_pool(store, account, generation, char["id"])
                self.assertEqual(pool["packet"][1][:2], b"\x00\x20")
                self.assertFalse(all_uids.intersection(pool["uids"]))
                all_uids.update(pool["uids"])
            with store.connection() as db:
                rows = db.execute(
                    "SELECT uid,used_request FROM inventory_reserved_uids WHERE account_id=? AND generation=?",
                    (account, generation),
                ).fetchall()
            self.assertEqual(len(rows), 33)
            self.assertEqual(dict(rows)[consumed], b"consumed-request")
            self.assertNotIn(old["uids"][1], dict(rows))

    def test_native_replenish_rejects_wrong_character_and_selector(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "world.sqlite3")
            account = store.register("pool-replenish", "local-password")["id"]
            char = store.create_character(account, "Pool Refill")
            generation = store.begin_session(account)
            store.select_character(account, generation, char["id"])
            for body in (
                b"",
                struct.pack(">qi", char["id"] + 1, 0),
                struct.pack(">qi", char["id"], 1),
            ):
                with self.assertRaises(ValueError):
                    replenish(store, account, generation, char["id"], body)
            result = replenish(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">qi", char["id"], 0),
            )
            self.assertEqual(result["packet"][1][:2], b"\x01\x20")
