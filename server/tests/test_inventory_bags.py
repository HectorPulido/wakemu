import struct
import unittest
from postgres_case import PostgresCase
from wakfu_server.inventory import bags
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_bags import remove, equip


class BagTests(PostgresCase):
    def test_empty_bag_removal_reconnect_and_reequip_preserve_uid(self):
        store = self.store
        account = store.register("bag-owner", "local-password")["id"]
        char = store.create_character(account, "Bag Owner")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        base, extra = (entry["uid"] for entry in char["inventory_containers"])
        result = remove(
            store,
            account,
            generation,
            char["id"],
            struct.pack(">qqqqb", base, extra, extra, base, 0),
        )
        self.assertEqual([code for code, _ in result["packets"]], [13172, 12471])
        current = self.reopen().character(account, char["id"])
        self.assertEqual(len(current["inventory_containers"]), 1)
        self.assertEqual(current["inventory_items"][0]["uid"], extra)
        # The held bag keeps its native binding option in the vj item form.
        self.assertEqual(len(bags(current)), 48)
        result = equip(
            store,
            account,
            generation,
            char["id"],
            struct.pack(">qqqb", extra, base, char["id"], 1),
        )
        self.assertEqual([code for code, _ in result["packets"]], [12470, 12919])
        self.assertEqual(result["packets"][0], (12470, struct.pack(">qh", extra, -1)))
        current = self.reopen().character(account, char["id"])
        self.assertEqual(current["inventory_containers"], char["inventory_containers"])
        self.assertEqual(current["inventory_items"], [])
        self.assertEqual(len(bags(current)), 42)

    def test_nonempty_fixed_full_and_stale_bags_fail_without_item_loss(self):
        store = self.store
        account = store.register("bag-guards", "local-password")["id"]
        char = store.create_character(account, "Bag Guards")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        base, extra = (entry["uid"] for entry in char["inventory_containers"])
        item = grant(
            store,
            account,
            generation,
            char["id"],
            reference=2021,
            quantity=1,
            container=extra,
            slot=0,
            allowed_references={2021},
        )
        for body in (
            struct.pack(">qqqqb", base, extra, extra, base, 0),
            struct.pack(">qqqqb", base, base, base, base, 0),
        ):
            with self.assertRaises(ValueError):
                remove(store, account, generation, char["id"], body)
        current = store.character(account, char["id"])
        self.assertEqual(current["inventory_containers"], char["inventory_containers"])
        self.assertEqual(current["inventory_items"], [item])
        # General inventory interoperability: move the contents out, then
        # remove the now-empty bag without losing the moved item.
        from wakfu_server.inventory_move import transfer

        moved = transfer(
            store,
            account,
            generation,
            char["id"],
            struct.pack(">qqqhB", item["uid"], base, extra, 1, 0),
        )
        self.assertEqual(moved["character"]["inventory_items"][0]["container"], base)
        removed = remove(
            store,
            account,
            generation,
            char["id"],
            struct.pack(">qqqqb", base, extra, extra, base, 0),
        )
        self.assertEqual(
            {i["uid"] for i in removed["character"]["inventory_items"]},
            {item["uid"], extra},
        )
        reloaded = self.reopen().character(account, char["id"])
        self.assertEqual(
            reloaded["inventory_items"], removed["character"]["inventory_items"]
        )
        with self.assertRaises(ValueError):
            # The equipped bag no longer exists; replay cannot create a duplicate.
            remove(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">qqqqb", base, extra, extra, base, 0),
            )
        store.begin_session(account)
        with self.assertRaises(ValueError):
            remove(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">qqqqb", base, extra, extra, base, 0),
            )

    def test_native_other_bag_capacity_level_reconnect_and_no_loss(self):
        store = self.store
        account = store.register("catalog-bag", "local-password")["id"]
        char = store.create_character(account, "Catalog Bag")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        base = char["inventory_containers"][0]["uid"]
        item = grant(
            store,
            account,
            generation,
            char["id"],
            reference=11898,
            quantity=1,
            container=base,
            slot=0,
            allowed_references={11898},
        )
        request = struct.pack(">qqqb", item["uid"], base, char["id"], 2)
        with self.assertRaises(ValueError):
            equip(store, account, generation, char["id"], request)
        self.assertEqual(
            store.character(account, char["id"])["inventory_items"], [item]
        )
        with store.connection() as db:
            db.execute("UPDATE characters SET level=30 WHERE id=%s", (char["id"],))
        result = equip(store, account, generation, char["id"], request)
        bag = result["character"]["inventory_containers"][2]
        self.assertEqual(
            (bag["reference"], bag["capacity"], bag["uid"]), (11898, 8, item["uid"])
        )
        self.assertEqual(len(bags(self.reopen().character(account, char["id"]))), 62)
        contained = grant(
            store,
            account,
            generation,
            char["id"],
            reference=2021,
            quantity=1,
            container=item["uid"],
            slot=7,
            allowed_references={2021},
        )
        with self.assertRaises(ValueError):
            grant(
                store,
                account,
                generation,
                char["id"],
                reference=2021,
                quantity=1,
                container=item["uid"],
                slot=8,
                allowed_references={2021},
            )
        body = struct.pack(">qqqqb", base, item["uid"], item["uid"], base, 0)
        with self.assertRaises(ValueError):
            remove(store, account, generation, char["id"], body)
        from wakfu_server.inventory_move import transfer

        transfer(
            store,
            account,
            generation,
            char["id"],
            struct.pack(">qqqhB", contained["uid"], base, item["uid"], 1, 0),
        )
        result = remove(store, account, generation, char["id"], body)
        self.assertEqual(
            {i["uid"] for i in result["character"]["inventory_items"]},
            {item["uid"], contained["uid"]},
        )

    def test_stacked_bag_splits_one_unit_and_replay_is_rejected(self):
        store = self.store
        account = store.register("stack-bag", "local-password")["id"]
        char = store.create_character(account, "Stack Bag")
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
        request = struct.pack(">qqqb", item["uid"], base, char["id"], 2)
        result = equip(store, account, generation, char["id"], request)
        current = store.character(account, char["id"])
        bag = next(c for c in current["inventory_containers"] if c["kind"] == 2)
        self.assertNotEqual(bag["uid"], item["uid"])
        self.assertEqual(bag["capacity"], 10)
        self.assertEqual(bag["reference"], 12493)
        self.assertEqual(current["inventory_items"][0]["quantity"], 2)
        self.assertEqual(
            result["packets"][0], (12470, struct.pack(">qh", item["uid"], -1))
        )
        self.assertEqual(
            struct.unpack(">q", result["packets"][1][1][12:20])[0], bag["uid"]
        )
        with self.assertRaises(ValueError):
            equip(store, account, generation, char["id"], request)
        self.assertEqual(
            store.character(account, char["id"])["inventory_items"],
            current["inventory_items"],
        )
        remove(
            store,
            account,
            generation,
            char["id"],
            struct.pack(">qqqqb", base, bag["uid"], bag["uid"], base, 1),
        )
        reopened = self.reopen().character(account, char["id"])
        self.assertEqual(sum(i["quantity"] for i in reopened["inventory_items"]), 3)
        self.assertEqual(
            {i["uid"] for i in reopened["inventory_items"]}, {item["uid"], bag["uid"]}
        )
