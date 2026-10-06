import struct
import unittest
from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_actions import destroy, use_request, RULES
from wakfu_server.wire import proto_field


class InventoryActionsTests(PostgresCase):
    def test_destroy_complete_stack_reconnect_and_duplicate_request(self):
        store = self.store
        account = store.register("destroy-owner", "local-password")["id"]
        char = store.create_character(account, "Destroy Owner")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
        item = grant(
            store,
            account,
            generation,
            char["id"],
            reference=2021,
            quantity=3,
            container=char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={2021},
        )
        body = struct.pack(">q", item["uid"])
        result = destroy(store, account, generation, char["id"], body)
        self.assertEqual(
            result["packets"], [(12470, struct.pack(">qh", item["uid"], -3))]
        )
        self.assertEqual(
            self.reopen().character(account, char["id"])["inventory_items"], []
        )
        with self.assertRaises(ValueError):
            destroy(store, account, generation, char["id"], body)

    def test_foreign_request_and_use_does_not_consume(self):
        store = self.store
        account = store.register("action-owner", "local-password")["id"]
        first = store.create_character(account, "Action First")
        second = store.create_character(account, "Action Second")
        generation = store.begin_session(account)
        store.select_character(account, generation, first["id"])
        item = grant(
            store,
            account,
            generation,
            first["id"],
            reference=2021,
            quantity=1,
            container=first["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={2021},
        )
        result = use_request(
            store,
            account,
            generation,
            first["id"],
            struct.pack(">qB", item["uid"], 0),
        )
        self.assertIsNone(result["rule"]["use_action_id"])
        self.assertEqual(
            store.character(account, first["id"])["inventory_items"][0]["quantity"],
            1,
        )
        store.select_character(account, generation, second["id"])
        with self.assertRaises(ValueError):
            destroy(
                store,
                account,
                generation,
                second["id"],
                struct.pack(">q", item["uid"]),
            )

    def test_destruction_rejects_equipped_unit_without_partial_mutation(self):
        store = self.store
        account = store.register("equipped-owner", "local-password")["id"]
        char = store.create_character(account, "Equipped Owner")
        generation = store.begin_session(account)
        store.select_character(account, generation, char["id"])
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
        equipment = proto_field(10, proto_field(8, item["uid"]) + proto_field(16, 4))
        with store.connection() as db:
            db.execute(
                "INSERT INTO character_builds VALUES(%s,%s,%s,%s,%s,%s)",
                (char["id"], 0, proto_field(24, (1 << 64) - 1), equipment, b"", b""),
            )
        with self.assertRaises(ValueError):
            destroy(
                store,
                account,
                generation,
                char["id"],
                struct.pack(">q", item["uid"]),
            )
        self.assertEqual(
            store.character(account, char["id"])["inventory_items"][0]["quantity"],
            1,
        )
