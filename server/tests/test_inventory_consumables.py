import struct
import tempfile
import unittest
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_consumables import use, healing_plan
from wakfu_server import health_store


class ConsumableTests(unittest.TestCase):
    def test_real_native_food_heals_consumes_caps_and_reconnects(self):
        self.assertEqual(healing_plan(3864)["amount"], 55)
        for reference in (2021, 18096, 31005):
            with self.assertRaises(ValueError):
                healing_plan(reference)
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "world.sqlite3")
            account = store.register("food-owner", "local-password")["id"]
            char = store.create_character(account, "Food Owner")
            generation = store.begin_session(account)
            store.select_character(account, generation, char["id"])
            health_store.initialize(
                store, account, generation, char["id"], coefficient=1
            )
            health_store.sync(
                store, account, generation, char["id"], 60, 10, coefficient=1
            )
            item = grant(
                store,
                account,
                generation,
                char["id"],
                reference=3864,
                quantity=2,
                container=char["inventory_containers"][0]["uid"],
                slot=0,
                allowed_references={3864},
            )
            body = struct.pack(">qB", item["uid"], 0)
            for options in (
                dict(expected_hp=11, in_fight=False),
                dict(expected_hp=10, in_fight=True),
            ):
                with self.assertRaises(ValueError):
                    use(store, account, generation, char["id"], body, **options)
            self.assertEqual(
                store.character(account, char["id"])["inventory_items"][0]["quantity"],
                2,
            )
            result = use(
                store,
                account,
                generation,
                char["id"],
                body,
                expected_hp=10,
                in_fight=False,
            )
            self.assertEqual((result["healed"], result["character"]["hp"]), (50, 60))
            self.assertEqual(
                result["packets"][0], (12470, struct.pack(">qh", item["uid"], -1))
            )
            self.assertEqual(
                result["packets"][1], (12436, struct.pack(">qii", char["id"], 60, 1))
            )
            fresh = Store(store.path).character(account, char["id"])
            self.assertEqual(
                (fresh["hp"], fresh["inventory_items"][0]["quantity"]), (60, 1)
            )
            with self.assertRaises(ValueError):
                use(
                    store,
                    account,
                    generation,
                    char["id"],
                    body,
                    expected_hp=60,
                    in_fight=False,
                )
            health_store.sync(store, account, generation, char["id"], 60, 1)
            result = use(
                store,
                account,
                generation,
                char["id"],
                body,
                expected_hp=1,
                in_fight=False,
            )
            self.assertEqual(result["character"]["inventory_items"], [])
            self.assertEqual(result["character"]["hp"], 56)

    def test_dead_and_foreign_use_do_not_consume(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "world.sqlite3")
            account = store.register("dead-food", "local-password")["id"]
            char = store.create_character(account, "Dead Food")
            other = store.create_character(account, "Other Food")
            generation = store.begin_session(account)
            store.select_character(account, generation, char["id"])
            item = grant(
                store,
                account,
                generation,
                char["id"],
                reference=3864,
                quantity=1,
                container=char["inventory_containers"][0]["uid"],
                slot=0,
                allowed_references={3864},
            )
            body = struct.pack(">qB", item["uid"], 0)
            health_store.initialize(store, account, generation, char["id"])
            health_store.sync(store, account, generation, char["id"], 60, 0)
            with self.assertRaises(ValueError):
                use(
                    store,
                    account,
                    generation,
                    char["id"],
                    body,
                    expected_hp=0,
                    in_fight=False,
                )
            store.select_character(account, generation, other["id"])
            health_store.initialize(store, account, generation, other["id"])
            health_store.sync(store, account, generation, other["id"], 60, 10)
            with self.assertRaises(ValueError):
                use(
                    store,
                    account,
                    generation,
                    other["id"],
                    body,
                    expected_hp=10,
                    in_fight=False,
                )
            self.assertEqual(
                store.character(account, char["id"])["inventory_items"][0]["quantity"],
                1,
            )
