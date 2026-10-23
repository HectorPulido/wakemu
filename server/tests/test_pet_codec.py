"""Original companion model0, rw ordering and PET-only publication contracts."""
import struct
import unittest
from unittest.mock import patch

from wakfu_server import pet_codec, mount_codec
from wakfu_server.mount_publication import pet_packet, equipment_changes
from test_mount_codec import NativeMountCodecTests


class CompanionPetCodecTests(unittest.TestCase):
    def state(self, definition=0):
        return dict(
            definition_id=definition,
            name="Miaumiau",
            color_item_ref=11,
            equipped_item_ref=12,
            sleep_item_ref=13,
            health=19,
            reskin_item_ref=14,
            xp=150,
            last_meal_date=1700000000000,
            last_hungry_date=1700000000000,
            sleep_date=1700000000000,
            daily_limit_enabled=True,
        )

    def test_original_valid_model_zero_has_present_protopet_field50(self):
        outer = NativeMountCodecTests._fields(pet_codec.item_pet(self.state()))
        self.assertEqual({50}, set(outer))
        fields = NativeMountCodecTests._fields(outer[50])
        self.assertEqual(0, fields[1])
        self.assertEqual(b"Miaumiau", fields[2])
        self.assertEqual((19, 150), (fields[5], fields[6]))
        self.assertEqual(1700000000000, fields[7])
        with self.assertRaises(ValueError):
            mount_codec.item_pet(self.state())

    def test_rw_first_companion_record_and_second_mount_record_match_original_bytes(
        self,
    ):
        pet = pet_codec.companion_section(self.state())
        mount = mount_codec.pet_section(self.state(76))[1:]
        self.assertEqual(b"\x01" + struct.pack(">6i", 0, 11, 12, 13, 19, 14), pet)
        self.assertEqual(b"\x01" + struct.pack(">6i", 76, 11, 12, 13, 19, 14), mount)
        self.assertEqual(b"\x00", pet_codec.companion_section(None))
        self.assertEqual(50, len(pet + mount))

    def test_daily_policy_masks_only_published_last_meal_timestamp(self):
        state = self.state()
        state["daily_limit_enabled"] = False
        fields = NativeMountCodecTests._fields(
            NativeMountCodecTests._fields(pet_codec.item_pet(state))[50]
        )
        self.assertEqual(0, fields[7])
        self.assertEqual(1700000000000, state["last_meal_date"])

    def test_pet_packet_uses_format29_id_and_pet_without_full_actor(self):
        character = dict(id=1234)
        record = pet_codec.companion_section(self.state()) + b"\x00"
        with patch("wakfu_server.mount_publication.actor_pet", return_value=record):
            opcode, body = pet_packet(character)
        self.assertEqual(13046, opcode)
        identity, size = struct.unpack_from(">qh", body)
        self.assertEqual(1234, identity)
        self.assertEqual(b"\x1d" + struct.pack(">q", 1234) + record, body[10:])
        self.assertEqual(size, len(body) - 10)

    def test_equipment_publication_orders_partial_pet_appearance_and_riding_result(
        self,
    ):
        previous = dict(
            id=1234, account_id=7, record=b"\x00\x00", mount_state=dict(mounted=False)
        )
        current = dict(
            previous, record=pet_codec.companion_section(self.state()) + b"\x00"
        )
        with patch(
            "wakfu_server.mount_publication.actor_pet",
            side_effect=lambda c: c["record"],
        ), patch(
            "wakfu_server.equipment_appearance.change_packet",
            return_value=(13060, b"appearance"),
        ):
            packets = equipment_changes(b"unused", previous, current)
        self.assertEqual([13046, 13060, 13928], [packet[0] for packet in packets])
        self.assertEqual(29, packets[0][1][10])
        self.assertNotIn(15548, [packet[0] for packet in packets])
