import struct
import uuid

from postgres_case import PostgresCase

from wakfu_server import wire
from wakfu_server.exchange_inventory import packets
from wakfu_server.inventory_items import grant, item_form


class ExchangeInventoryTests(PostgresCase):
    def player(self):
        account = self.store.register(
            f"exchange-inventory-{uuid.uuid4().hex[:10]}",
            "exchange-inventory-test-password",
        )["id"]
        character = self.store.create_character(account, "Exchange Inventory")
        generation = self.store.begin_session(account)
        character = self.store.select_character(account, generation, character["id"])
        return account, generation, character

    def grant_item(self, account, generation, character, reference, slot):
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=reference,
            quantity=1,
            container=character["inventory_containers"][0]["uid"],
            slot=slot,
            allowed_references={reference},
        )

    def test_reconciliation_replaces_bags_and_registry_with_mount_proto_intact(self):
        account, generation, character = self.player()
        regular = self.grant_item(account, generation, character, 12, 0)
        mount = self.grant_item(account, generation, character, 14422, 1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET name='Exchange mount',xp=321,health=19,"
                "color_item_ref=8,equipped_item_ref=9,sleep_item_ref=0,sleep_date=0,"
                "last_meal_date=123000,last_hungry_date=456000 WHERE uid=%s",
                (mount["uid"],),
            )
        character = self.store.character(account, character["id"])
        mount_unit = next(
            item for item in character["inventory_items"] if item["uid"] == mount["uid"]
        )
        old_uid, offered_uid = 700_000_000_001, 700_000_000_002
        transfers = {
            "previous_uids": {str(character["id"]): [old_uid, regular["uid"]]},
            "offered_uids": [offered_uid, regular["uid"]],
        }

        result = packets(character, transfers)

        self.assertEqual([13713, 13078], [opcode for opcode, _ in result])
        self.assertNotIn(12919, [opcode for opcode, _ in result])
        self.assertNotIn(12471, [opcode for opcode, _ in result])

        bag_opcode, bag_body = result[0]
        self.assertEqual(13713, bag_opcode)
        self.assertEqual((character["id"], 35), struct.unpack_from(">qB", bag_body))
        bag_bytes = bag_body[9:]
        container_count = struct.unpack_from(">H", bag_bytes)[0]
        self.assertEqual(len(character["inventory_containers"]), container_count)
        by_container = {row["uid"]: row for row in character["inventory_containers"]}
        items_by_container = {}
        for item in character["inventory_items"]:
            items_by_container.setdefault(item["container"], []).append(item)
        offset = 2
        bag_headers = []
        for _ in range(container_count):
            header = struct.unpack_from(">qiBhBH", bag_bytes, offset)
            offset += struct.calcsize(">qiBhBH")
            bag_uid, reference, kind, capacity, flags, item_count = header
            expected_container = by_container[bag_uid]
            self.assertEqual(
                (
                    expected_container["reference"],
                    expected_container["kind"],
                    expected_container["capacity"],
                    expected_container["flags"],
                ),
                (reference, kind, capacity, flags),
            )
            contents = sorted(
                items_by_container.get(bag_uid, []), key=lambda row: row["slot"]
            )
            self.assertEqual(len(contents), item_count)
            bag_headers.append((bag_uid, item_count))
            for item in contents:
                slot = struct.unpack_from(">h", bag_bytes, offset)[0]
                offset += 2
                self.assertEqual(item["slot"], slot)
                form = item_form(item)
                self.assertEqual(form, bag_bytes[offset : offset + len(form)])
                self.assertEqual(
                    (item["uid"], item["reference"], item["quantity"]),
                    struct.unpack_from(">qih", bag_bytes, offset),
                )
                offset += len(form)
            self.assertEqual(b"\x00\x00", bag_bytes[offset : offset + 2])
            offset += 2
        self.assertEqual(len(bag_bytes), offset)
        self.assertEqual(
            [
                (character["inventory_containers"][0]["uid"], 2),
                (character["inventory_containers"][1]["uid"], 0),
            ],
            bag_headers,
        )

        registry_opcode, registry_body = result[1]
        self.assertEqual(13078, registry_opcode)
        registry_owner, registry_length, compressed = struct.unpack_from(
            ">qIB", registry_body
        )
        self.assertEqual((character["id"], 0), (registry_owner, compressed))
        self.assertEqual(registry_length, len(registry_body) - 13)
        registry_items = [
            value for tag, value in wire.proto_fields(registry_body[13:]) if tag == 10
        ]
        self.assertEqual(2, len(registry_items))
        item_by_uid = {item["uid"]: item for item in character["inventory_items"]}
        decoded_registry = {}
        for proto in registry_items:
            fields = list(wire.proto_fields(proto))
            identity = next(value for tag, value in fields if tag == 8)
            decoded_registry[identity] = fields
        self.assertEqual({regular["uid"], mount["uid"]}, set(decoded_registry))
        self.assertNotIn(old_uid, decoded_registry)
        self.assertNotIn(offered_uid, decoded_registry)
        for identity, fields in decoded_registry.items():
            parsed = {tag: value for tag, value in fields}
            item = item_by_uid[identity]
            self.assertEqual(
                (item["reference"], item["quantity"]), (parsed[16], parsed[24])
            )

        mount_fields = decoded_registry[mount["uid"]]
        pet_fields = [value for tag, value in mount_fields if tag == 402]
        self.assertEqual(1, len(pet_fields))
        pet = {tag >> 3: value for tag, value in wire.proto_fields(pet_fields[0])}
        self.assertEqual(
            {
                1: mount_unit["mount"]["definition_id"],
                2: b"Exchange mount",
                3: 8,
                4: 9,
                5: 19,
                6: 321,
                7: 123000,
                8: 456000,
                9: 0,
                10: 0,
            },
            pet,
        )

    def test_reconciliation_rejects_foreign_snapshots_and_incomplete_receipts(self):
        account, generation, character = self.player()
        character["inventory_items"] = [
            {
                "uid": 100,
                "character_id": character["id"] + 1,
                "reference": 12,
                "quantity": 1,
                "container": character["inventory_containers"][0]["uid"],
                "slot": 0,
            }
        ]
        valid_receipt = {
            "previous_uids": {str(character["id"]): []},
            "offered_uids": [],
        }
        with self.assertRaisesRegex(ValueError, "Foreign"):
            packets(character, valid_receipt)

        character = self.store.character(account, character["id"])
        for receipt in (
            {},
            {"previous_uids": {}, "offered_uids": []},
            {"previous_uids": {str(character["id"]): []}},
            {"previous_uids": {str(character["id"]): None}, "offered_uids": []},
            {"previous_uids": {str(character["id"]): []}, "offered_uids": None},
        ):
            with self.subTest(receipt=receipt), self.assertRaisesRegex(
                ValueError, "receipt"
            ):
                packets(character, receipt)
