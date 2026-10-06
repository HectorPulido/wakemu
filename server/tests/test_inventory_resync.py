import struct
from postgres_case import PostgresCase
from wakfu_server.inventory import bags
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_bags import equip
from wakfu_server.inventory_move import reload_inventory, synchronization


class InventoryResyncTests(PostgresCase):
    def test_rejected_stacked_bag_recovers_committed_inventory_only(self):
        store = self.store
        account = store.register("resync-owner", "local-password")["id"]
        character = store.create_character(account, "Resync Owner")
        generation = store.begin_session(account)
        store.select_character(account, generation, character["id"])
        container = character["inventory_containers"][0]["uid"]
        item = grant(
            store,
            account,
            generation,
            character["id"],
            reference=2603,
            quantity=3,
            container=container,
            slot=0,
            allowed_references={2603},
        )
        with self.assertRaises(ValueError):
            equip(
                store,
                account,
                generation,
                character["id"],
                struct.pack(">qqqb", item["uid"], container, character["id"], 1),
            )
        live = dict(character, hp=7, x=999, instance_id=123, xp=456)
        refreshed = reload_inventory(store, account, live)
        self.assertEqual(refreshed["inventory_items"], [item])
        for field in ("hp", "x", "instance_id", "xp"):
            self.assertEqual(refreshed[field], live[field])
        self.assertEqual(character["inventory_items"], [])
        code, body = synchronization(refreshed)
        self.assertEqual(code, 13713)
        self.assertEqual(struct.unpack(">qB", body[:9]), (character["id"], 35))
        self.assertEqual(body[9:], bags(store.character(account, character["id"])))
        self.assertEqual(
            store.character(account, character["id"])["inventory_items"], [item]
        )

    def test_empty_snapshot_also_selects_bags_format(self):
        account = self.store.register("empty-owner", "local-password")["id"]
        character = self.store.create_character(account, "Empty Owner")
        body = synchronization(character)[1]
        self.assertEqual(body[8], 35)
        self.assertEqual(body[9:], bags(character))

    def test_action_rejections_recover_same_committed_items(self):
        from wakfu_server.inventory_actions import destroy
        from wakfu_server.inventory_consumables import use
        from wakfu_server.inventory_move import transfer

        store = self.store
        account = store.register("reject-owner", "local-password")["id"]
        char = store.create_character(account, "Reject Owner")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        base = char["inventory_containers"][0]["uid"]
        item = grant(
            store,
            account,
            generation,
            char["id"],
            reference=12493,
            quantity=3,
            container=base,
            slot=0,
            allowed_references={12493},
        )
        operations = {
            "destroy_missing": lambda: destroy(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">q", item["uid"] + 999),
            ),
            "consume_in_combat": lambda: use(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">qB", item["uid"], 0),
                expected_hp=char["hp"],
                in_fight=True,
            ),
            "transfer_outside_capacity": lambda: transfer(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">qqqhB", item["uid"], base, base, 30, 0),
            ),
        }
        for name, operation in operations.items():
            with self.subTest(operation=name):
                with self.assertRaises(ValueError):
                    operation()
                recovered = reload_inventory(store, account, char)
                self.assertEqual(recovered["inventory_items"], [item])
                self.assertEqual(synchronization(recovered)[1][9:], bags(recovered))
