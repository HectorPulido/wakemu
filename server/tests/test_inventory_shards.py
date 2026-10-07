import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant, item_form, item_proto
from wakfu_server.inventory_shards import copy as copy_shards, save, validate
from wakfu_server.element_selection import select as select_elements
from wakfu_server.wire import proto_field, proto_fields
from wakfu_server.exchange_transfer import (
    apply as apply_exchange,
    plan as plan_exchange,
)


def sample_shard_state():
    slot = b"".join(
        (
            proto_field(80, 1),
            proto_field(88, 2468),
            proto_field(96, 4),
            proto_field(112, 2),
        )
    )
    gem = b"".join((proto_field(160, 3), proto_field(168, 13579)))
    return b"".join(
        (
            proto_field(10, slot),
            proto_field(18, gem),
            proto_field(24, 901),
            proto_field(32, 902),
            proto_field(72, 7),
        )
    )


class InventoryShardsTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("shard-state", "local-test-password")["id"]
        self.char = self.store.create_character(self.account, "Shard State")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])
        self.bag = self.char["inventory_containers"][0]["uid"]
        self.item = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=2869,
            quantity=1,
            container=self.bag,
            slot=0,
            allowed_references={2869},
        )

    def test_native_proto_shard_and_legacy_inventory_option_survive_reopen(self):
        state = sample_shard_state()
        with self.store.connection() as db:
            save(db, self.item["uid"], state)
        selected = select_elements(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            struct.pack(">qBB", self.item["uid"], 22, 0),
        )
        self.assertEqual(selected["shard_state"], state)
        self.assertTrue(selected["packet"][1].endswith(state))

        reopened = self.reopen().character(self.account, self.char["id"])
        item = next(
            row for row in reopened["inventory_items"] if row["uid"] == self.item["uid"]
        )
        self.assertEqual(item["shard_state"], state)
        proto = dict(proto_fields(item_proto(item)))
        self.assertEqual(proto[418], state)  # ProtoItem.shard, field 52.

        form = item_form(item)
        options = form[14:]
        self.assertEqual(options[:3], bytes((0, 0, 1)))  # vv, vE, vA.
        expected_option = struct.pack(
            ">HBiBiHBi iiB".replace(" ", ""),
            1,
            1,
            2468,
            4,
            2,
            1,
            3,
            13579,
            901,
            902,
            7,
        )
        self.assertEqual(options[3 : 3 + len(expected_option)], expected_option)
        self.assertEqual(
            options[3 + len(expected_option) :],
            bytes(
                (0, 0, 1, item["damage_elements"], item["resistance_elements"], 0, 0)
            ),
        )

    def test_socket_state_copy_preserves_exact_blob_for_new_unit_uid(self):
        state = sample_shard_state()
        target = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=2869,
            quantity=1,
            container=self.bag,
            slot=1,
            allowed_references={2869},
        )
        with self.store.connection() as db:
            save(db, self.item["uid"], state)
            copy_shards(db, self.item["uid"], target["uid"])
            row = db.execute(
                "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                (target["uid"],),
            ).fetchone()
        self.assertEqual(bytes(row["shard_state"]), state)

    def test_whole_exchange_transfer_preserves_native_shard_state(self):
        state = sample_shard_state()
        recipient_account = self.store.register(
            "shard-recipient", "local-test-password"
        )["id"]
        recipient = self.store.create_character(recipient_account, "Shard Recipient")
        with self.store.connection() as db:
            save(db, self.item["uid"], state)
            original = [
                *self.store_items(db, self.char["id"]),
                *self.store_items(db, recipient["id"]),
            ]
            containers = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM inventory_containers WHERE character_id=ANY(%s)",
                    ([self.char["id"], recipient["id"]],),
                )
            ]
            final, _ = plan_exchange(
                original,
                containers,
                [dict(uid=self.item["uid"], quantity=1, character_id=self.char["id"])],
                allocate=lambda: 987654321,
            )
            apply_exchange(db, original, final)
            loaded = self.store_items(db, recipient["id"])
        moved = next(row for row in loaded if row["uid"] == self.item["uid"])
        self.assertEqual(moved["shard_state"], state)

    @staticmethod
    def store_items(db, character_id):
        from wakfu_server.inventory_items import load

        return load(db, character_id)

    def test_unknown_fields_are_preserved_but_known_wire_types_are_checked(self):
        state = sample_shard_state() + proto_field(99 << 3 | 0, 123)
        self.assertEqual(validate(state), state)
        unknown_field = proto_field(99 << 3, 42)
        self.assertEqual(validate(unknown_field), unknown_field)
        # Known protobuf field numbers with a wrong wire type cannot be safely
        # represented in the legacy inventory option.
        with self.assertRaisesRegex(ValueError, "wire type"):
            validate(bytes((8, 42)))
        with self.assertRaisesRegex(ValueError, "wire type"):
            validate(proto_field(10, bytes((82, 0))))
        with self.assertRaises(ValueError):
            validate(proto_field(10, b"\x0a\x02\x01"))
        with self.assertRaisesRegex(ValueError, "size"):
            validate(b"")
        with self.assertRaisesRegex(ValueError, "size"):
            validate(b"x" * 65537)


if __name__ == "__main__":
    unittest.main()
