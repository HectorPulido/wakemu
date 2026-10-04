import struct
import tempfile
import unittest
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_move import transfer, decode


class InventoryMoveTests(unittest.TestCase):
    def test_native_whole_move_persists_without_duplicate_client_insert(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "world.sqlite3")
            account = store.register("mover", "local-password")["id"]
            char = store.create_character(account, "Item Mover")
            generation = store.begin_session(account)
            store.select_character(account, generation, char["id"])
            bag = char["inventory_containers"][0]["uid"]
            item = grant(
                store,
                account,
                generation,
                char["id"],
                reference=2021,
                quantity=1,
                container=bag,
                slot=0,
                allowed_references={2021},
            )
            body = struct.pack(">qqqhB", item["uid"], bag, bag, 5, 0)
            result = transfer(store, account, generation, char["id"], body)
            self.assertEqual(result["packets"], [])
            self.assertEqual(result["character"]["inventory_items"][0]["slot"], 5)
            self.assertEqual(
                Store(store.path).character(account, char["id"])["inventory_items"][0][
                    "slot"
                ],
                5,
            )
            grant(
                store,
                account,
                generation,
                char["id"],
                reference=2021,
                quantity=1,
                container=bag,
                slot=6,
                allowed_references={2021},
            )
            self.assertEqual(
                store.character(account, char["id"])["inventory_items"][0]["slot"], 5
            )
            with self.assertRaises(ValueError):
                transfer(
                    store,
                    account,
                    generation,
                    char["id"],
                    struct.pack(">qqqhB", item["uid"], bag, bag, 30, 0),
                )
            store.begin_session(account)
            with self.assertRaises(ValueError):
                transfer(store, account, generation, char["id"], body)

    def test_split_header_requires_positive_owned_clone_and_partial_quantity(self):
        self.assertEqual(
            decode(struct.pack(">qqqhBqh", 1, 640, 640, 1, 1, 2, 1))["clone_uid"], 2
        )
        with self.assertRaises(ValueError):
            decode(struct.pack(">qqqhBqh", 1, 640, 640, 1, 1, 1, 1))

    def test_reserved_partial_replay_and_native_merge_cap_conserve_quantity(self):
        from wakfu_server.inventory_uids import reserve

        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "world.sqlite3")
            account = store.register("splitter", "local-password")["id"]
            char = store.create_character(account, "Item Splitter")
            generation = store.begin_session(account)
            store.select_character(account, generation, char["id"])
            bag = char["inventory_containers"][0]["uid"]
            first = grant(
                store,
                account,
                generation,
                char["id"],
                reference=2021,
                quantity=10,
                container=bag,
                slot=0,
                allowed_references={2021},
            )
            pool = reserve(store, account, generation, char["id"], count=2)
            clone = pool["uids"][0]
            body = struct.pack(">qqqhBqh", first["uid"], bag, bag, 1, 1, clone, 3)
            split = transfer(store, account, generation, char["id"], body)
            self.assertEqual(
                {
                    i["uid"]: i["quantity"]
                    for i in split["character"]["inventory_items"]
                },
                {first["uid"]: 7, clone: 3},
            )
            self.assertFalse(
                transfer(store, account, generation, char["id"], body)["applied"]
            )
            with self.assertRaises(ValueError):
                transfer(
                    store,
                    account,
                    generation,
                    char["id"],
                    struct.pack(">qqqhBqh", first["uid"], bag, bag, 2, 1, clone, 2),
                )
            target = grant(
                store,
                account,
                generation,
                char["id"],
                reference=2021,
                quantity=98,
                container=bag,
                slot=2,
                allowed_references={2021},
            )
            merged = transfer(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">qqqhB", clone, bag, bag, 2, 0),
            )
            quantities = {
                i["uid"]: i["quantity"] for i in merged["character"]["inventory_items"]
            }
            self.assertEqual((quantities[clone], quantities[target["uid"]]), (2, 99))
            self.assertEqual(sum(quantities.values()), 108)
            invalid = struct.pack(
                ">qqqhBqh", first["uid"], bag, bag, 3, 1, clone + 100, 1
            )
            with self.assertRaises(ValueError):
                transfer(store, account, generation, char["id"], invalid)

    def test_distinct_minimal_items_swap_owned_positions(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "world.sqlite3")
            account = store.register("swapper", "local-password")["id"]
            char = store.create_character(account, "Item Swapper")
            generation = store.begin_session(account)
            store.select_character(account, generation, char["id"])
            bag = char["inventory_containers"][0]["uid"]
            items = [
                grant(
                    store,
                    account,
                    generation,
                    char["id"],
                    reference=ref,
                    quantity=1,
                    container=bag,
                    slot=slot,
                    allowed_references={ref},
                )
                for slot, ref in enumerate((2021, 2023))
            ]
            body = struct.pack(">qqqhB", items[0]["uid"], bag, bag, 1, 0)
            result = transfer(store, account, generation, char["id"], body)
            self.assertEqual(
                {i["uid"]: i["slot"] for i in result["character"]["inventory_items"]},
                {items[0]["uid"]: 1, items[1]["uid"]: 0},
            )
            self.assertFalse(
                transfer(store, account, generation, char["id"], body)["applied"]
            )
