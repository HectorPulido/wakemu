import struct
import unittest

from wakfu_server import mount_codec


class NativeMountCodecTests(unittest.TestCase):
    def test_pet_section_matches_rw_and_rz_layout(self):
        state = {
            "definition_id": 76,
            "color_item_ref": 11,
            "equipped_item_ref": 12,
            "sleep_item_ref": 13,
            "health": 19,
            "reskin_item_ref": 14,
        }
        self.assertEqual(
            mount_codec.pet_section(state),
            b"\x00\x01" + struct.pack(">6i", 76, 11, 12, 13, 19, 14),
        )
        self.assertEqual(len(mount_codec.pet_section(state)), 26)

    def test_item_pet_matches_protoitem_field50_with_signed_dates(self):
        state = {
            "definition_id": 76,
            "name": "Drago ñ",
            "color_item_ref": 11,
            "equipped_item_ref": 12,
            "health": 19,
            "xp": 1234,
            "last_meal_date": -1,
            "last_hungry_date": 0,
            "sleep_item_ref": 13,
            "sleep_date": (1 << 63) - 1,
        }
        # Captured from the native kX/ProtoPet field-number contract. In
        # particular, ProtoItem field 50 wraps the nested ProtoPet message;
        # negative int64 is sign-extended protobuf varint, not zig-zag.
        expected = bytes.fromhex(
            "9203"  # ProtoItem field 50, length-delimited
            "2e"  # ProtoPet payload length
            "084c"  # 1 definitionId = 76
            "1208447261676f20c3b1"  # 2 name = UTF-8 Drago ñ
            "180b"  # 3 colorItemRefId = 11
            "200c"  # 4 equippedRefItemId = 12
            "2813"  # 5 health = 19
            "30d209"  # 6 xp = 1234
            "38ffffffffffffffffff01"  # 7 lastMealDate = -1
            "4000"  # 8 lastHungryDate = 0
            "480d"  # 9 sleepRefItemId = 13
            "50ffffffffffffffff7f"  # 10 sleepDate = INT64_MAX
        )
        self.assertEqual(mount_codec.item_pet(state), expected)

    def test_entity_refresh_uses_native_signed_character_and_length(self):
        entity = b"\x00\x01\x00\x00"  # opaque entity bytes, not decoded here
        opcode, body = mount_codec.entity_refresh(34, entity)
        self.assertEqual(opcode, 15548)
        self.assertEqual(body, struct.pack(">qh", 34, len(entity)) + entity)

    def test_pet_and_proto_integer_ranges_reject_invalid_values(self):
        state = {
            "definition_id": 76,
            "name": "Mount",
            "color_item_ref": 0,
            "equipped_item_ref": 0,
            "sleep_item_ref": 0,
            "health": 20,
            "reskin_item_ref": 0,
            "xp": 0,
            "last_meal_date": 0,
            "last_hungry_date": 0,
            "sleep_date": 0,
        }
        for invalid in (True, -1, 1 << 31, "1"):
            with self.subTest(invalid=invalid):
                candidate = dict(state, health=invalid)
                with self.assertRaises(ValueError):
                    mount_codec.pet_section(candidate)
                with self.assertRaises(ValueError):
                    mount_codec.item_pet(candidate)
        for key, invalid in (
            ("last_meal_date", -(1 << 63) - 1),
            ("last_hungry_date", 1 << 63),
            ("sleep_date", False),
        ):
            with self.subTest(key=key, invalid=invalid):
                with self.assertRaises(ValueError):
                    mount_codec.item_pet(dict(state, **{key: invalid}))
        with self.assertRaises(ValueError):
            mount_codec.item_pet(dict(state, definition_id=0))
        with self.assertRaises(ValueError):
            mount_codec.pet_section(dict(state, definition_id=0))

    def test_pet_absence_and_refresh_body_bounds(self):
        no_xp_state = {
            "definition_id": 76,
            "color_item_ref": 0,
            "equipped_item_ref": 0,
            "sleep_item_ref": 0,
            "health": 20,
            "reskin_item_ref": 0,
        }
        self.assertEqual(len(mount_codec.pet_section(no_xp_state)), 26)
        for character_id in (0, -1, 1 << 63, True):
            with self.subTest(character_id=character_id):
                with self.assertRaises(ValueError):
                    mount_codec.entity_refresh(character_id, b"x")
        for entity in (b"", b"x" * 32768, bytearray(b"x")):
            with self.subTest(entity_type=type(entity).__name__, size=len(entity)):
                with self.assertRaises(ValueError):
                    mount_codec.entity_refresh(1, entity)
        self.assertEqual(len(mount_codec.entity_refresh(1, b"x" * 32767)[1]), 32777)


if __name__ == "__main__":
    unittest.main()
