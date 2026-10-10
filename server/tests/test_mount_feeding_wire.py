import os
import struct
import unittest

from wakfu_server import mount_feeding_wire, mount_codec


class MountFeedingWireTests(unittest.TestCase):
    def test_native_payload_fixture_roundtrips(self):
        # ddX sets oa(pet UID) and nx(food UID); crX.aWH writes pet UID,
        # food UID, then quantity with
        # ByteBuffer.putLong/putLong/putInt (big-endian by default).
        payload = bytes.fromhex("0000000000000123 0000000000000456 00000002")
        self.assertEqual(
            mount_feeding_wire.decode_request(payload),
            {"food_uid": 0x456, "pet_uid": 0x123, "quantity": 2},
        )
        self.assertEqual(mount_feeding_wire.encode_request(0x456, 0x123, 2), payload)
        self.assertEqual(mount_feeding_wire.OPCODE, 12767)

    def test_rejects_bad_length_and_nonpositive_values(self):
        valid = mount_feeding_wire.encode_request(1, 2, 1)
        for payload in (valid[:-1], valid + b"\x00", b"\x00" * 20):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    mount_feeding_wire.decode_request(payload)

    def test_rejects_uid_and_quantity_out_of_wire_domain(self):
        for args in (
            (True, 2, 1),
            (0, 2, 1),
            (1, -1, 1),
            (1, 2, 0),
            (1, 2, 32768),
            (1, 2, True),
            (1 << 63, 2, 1),
        ):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    mount_feeding_wire.encode_request(*args)

        for payload in (
            struct.pack(">qqi", -1, 2, 1),
            struct.pack(">qqi", 1, 2, 32768),
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    mount_feeding_wire.decode_request(payload)

    @unittest.skipUnless(
        os.environ.get("WAKFU_DATABASE_URL"),
        "insertion serialization loads the native protocol catalog from PostgreSQL",
    )
    def test_publication_removes_consumed_food_then_recreates_same_pet_uid(self):
        food = {"uid": 100, "quantity": 3}
        pet = {
            "uid": 200,
            "reference": 18682,
            "quantity": 1,
            "container": 900,
            "slot": 5,
            "character_id": 77,
            "mount": {
                "definition_id": 76,
                "name": "Mount",
                "color_item_ref": 0,
                "equipped_item_ref": 0,
                "health": 20,
                "xp": 50,
                "last_meal_date": 123000,
                "last_hungry_date": 123000,
                "sleep_item_ref": 0,
                "sleep_date": 0,
            },
        }
        packets = mount_feeding_wire.publication_packets(food, pet, 2)
        self.assertEqual([opcode for opcode, _ in packets], [12470, 12470, 12471])
        self.assertEqual(packets[0], (12470, struct.pack(">qh", 100, -2)))
        self.assertEqual(packets[1], (12470, struct.pack(">qh", 200, -1)))
        container, slot, size = struct.unpack_from(">qhI", packets[2][1])
        self.assertEqual((container, slot), (900, 5))
        proto = packets[2][1][14 : 14 + size]
        self.assertIn(mount_codec.item_pet(pet["mount"]), proto)

    def test_publication_rejects_stacked_pet_and_uid_alias(self):
        food = {"uid": 10, "quantity": 1}
        pet = {"uid": 11, "quantity": 2}
        with self.assertRaises(ValueError):
            mount_feeding_wire.publication_packets(food, pet, 1)
        with self.assertRaises(ValueError):
            mount_feeding_wire.publication_packets(
                food, dict(pet, uid=10, quantity=1), 1
            )


if __name__ == "__main__":
    unittest.main()
