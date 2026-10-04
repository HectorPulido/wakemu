import tempfile
import unittest
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server.inventory import bags


class InventoryTests(unittest.TestCase):
    def test_equipment_registry_resolves_owned_units_independently_of_bags(self):
        import struct
        from wakfu_server.inventory_items import equipment_inventory
        from wakfu_server import wire

        item = dict(uid=1099511628389, character_id=7, reference=2021, quantity=1)
        character = dict(id=7, level=6, inventory_items=[item])
        opcode, body = equipment_inventory(character)
        self.assertEqual(opcode, 13078)
        owner, size, compressed = struct.unpack_from(">qIB", body)
        self.assertEqual((owner, size, compressed), (7, len(body) - 13, 0))
        entries = list(wire.proto_fields(body[13:]))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], 10)
        self.assertEqual(
            dict(wire.proto_fields(entries[0][1])), {8: item["uid"], 16: 2021, 24: 1}
        )
        self.assertEqual(wire.adapt(13078, b"old", 6, character), body)
        self.assertEqual(
            equipment_inventory(dict(character, inventory_items=[]))[1],
            struct.pack(">qIB", 7, 0, 0),
        )
        with self.assertRaises(ValueError):
            equipment_inventory(
                dict(character, inventory_items=[dict(item, character_id=8)])
            )
        with self.assertRaises(ValueError):
            equipment_inventory(dict(character, inventory_items=[item, item]))

    def test_empty_capacity_is_owned_persistent_and_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "world.sqlite3")
            account = store.register("inventory-owner", "local-password")["id"]
            first = store.create_character(account, "Inventory First")
            second = store.create_character(account, "Inventory Second")
            self.assertEqual(
                [c["capacity"] for c in first["inventory_containers"]], [30, 4]
            )
            self.assertEqual(len(bags(first)), 42)
            self.assertNotEqual(bags(first), bags(second))
            reopened = Store(store.path)
            self.assertEqual(
                reopened.character(account, first["id"])["inventory_containers"],
                first["inventory_containers"],
            )
            forged = {**first, "inventory_containers": second["inventory_containers"]}
            with self.assertRaises(ValueError):
                bags(forged)

    def test_basic_haven_contains_one_owned_gem_and_eight_empty_slots(self):
        from wakfu_server.haven_bag_store import initial_layout

        rooms = initial_layout(2)
        self.assertEqual([r["index"] for r in rooms if r["enabled"]], [0])
        self.assertEqual(
            [
                (r["primary_ref"], r["primary_uid"])
                for r in rooms
                if r["primary_ref"] != -1
            ],
            [(4262, 513)],
        )
        self.assertTrue(
            all(r["secondary_ref"] == -1 and r["secondary_uid"] == 0 for r in rooms)
        )

    def test_explicit_owned_items_reload_and_removal_is_lease_scoped(self):
        from wakfu_server.inventory_items import grant, remove, insertion
        import struct

        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "items.sqlite3", lambda: 1000)
            account = store.register("item-owner", "local-password")["id"]
            character = store.create_character(account, "Item Owner")
            sibling = store.create_character(account, "Item Sibling")
            generation = store.begin_session(account)
            store.select_character(account, generation, character["id"])
            destination = character["inventory_containers"][0]["uid"]
            item = grant(
                store,
                account,
                generation,
                character["id"],
                reference=100,
                quantity=3,
                container=destination,
                slot=0,
                allowed_references={100},
            )
            self.assertGreater(item["uid"], 1 << 40)
            self.assertEqual(insertion(item)[0], 12471)
            reloaded = store.character(account, character["id"])
            self.assertEqual(reloaded["inventory_items"], [item])
            self.assertEqual(len(bags(reloaded)), 66)
            self.assertEqual(
                store.character(account, sibling["id"])["inventory_items"], []
            )
            with self.assertRaises(ValueError):
                remove(store, account, generation, sibling["id"], item["uid"], 1)
            with self.assertRaises(ValueError):
                remove(store, account, generation, character["id"], item["uid"], 4)
            self.assertEqual(
                remove(store, account, generation, character["id"], item["uid"], 2),
                (12470, struct.pack(">qh", item["uid"], -2)),
            )
            self.assertEqual(
                store.character(account, character["id"])["inventory_items"][0][
                    "quantity"
                ],
                1,
            )
            store.begin_session(account)
            with self.assertRaises(ValueError):
                remove(store, account, generation, character["id"], item["uid"], 1)
