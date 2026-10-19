import copy
import hashlib
import struct
import unittest
from unittest.mock import patch

from wakfu_server import wire
from wakfu_server.items.equipment_appearance import rows, section, change_packet
from wakfu_server.items.mount_publication import equipment_changes


class EquipmentAppearanceTests(unittest.TestCase):
    def character(self):
        return dict(
            id=1,
            account_id=2,
            level=6,
            breed=8,
            active_build_index=0,
            inventory_items=[
                dict(uid=1001, character_id=1, reference=6823, quantity=1)
            ],
            builds={
                0: dict(
                    sheet=wire.proto_field(24, (1 << 64) - 1).hex(),
                    equipment=wire.proto_field(
                        10, wire.proto_field(8, 1001) + wire.proto_field(16, 0)
                    ).hex(),
                )
            },
        )

    def test_owned_hat_reaches_native_remote_and_owned_entity_sections(self):
        character = self.character()
        original = copy.deepcopy(character)
        expected = struct.pack(">BBii", 1, 0, 6823, 0)
        self.assertEqual(rows(character), ((0, 6823, 0),))
        self.assertEqual(section(character), expected)
        for kind in (5, 10, 11):
            template = bytes((kind,)) + b"prefix" + b"\x00" + b"suffix"
            layout = dict(
                template_sha256=hashlib.sha256(template).hexdigest(),
                sections=[dict(name="EQUIPMENT_APPEARANCE", start=7, end=8)],
            )
            with self.subTest(kind=kind), patch.dict(
                wire.ENTITY_LAYOUTS, {kind: layout}
            ):
                self.assertEqual(
                    wire.minimal_entity(template, character),
                    template[:7] + expected + template[8:],
                )
        self.assertEqual(character, original)

    def test_active_build_only_and_explicit_unequip_delta(self):
        equipped = self.character()
        empty = copy.deepcopy(equipped)
        empty["builds"][0]["equipment"] = wire.proto_field(424, 6).hex()
        self.assertEqual(
            change_packet(empty, equipped),
            (13060, struct.pack(">qBBii", 1, 1, 0, 6823, 6823)),
        )
        self.assertEqual(
            change_packet(equipped, empty),
            (13060, struct.pack(">qBBii", 1, 1, 0, 0, 0)),
        )
        self.assertEqual(section(empty), b"\x00")
        self.assertIsNone(change_packet(equipped, copy.deepcopy(equipped)))

    def test_normal_equipment_publishes_without_mount_recreation(self):
        equipped = self.character()
        empty = copy.deepcopy(equipped)
        empty["builds"][0]["equipment"] = wire.proto_field(424, 6).hex()
        self.assertEqual(
            equipment_changes(b"unused", empty, equipped),
            [change_packet(empty, equipped)],
        )
        self.assertEqual(
            equipment_changes(b"unused", equipped, empty),
            [change_packet(equipped, empty)],
        )

    def test_projection_rejects_foreign_units_and_invalid_active_build(self):
        character = self.character()
        character["inventory_items"][0]["character_id"] = 99
        with self.assertRaises(ValueError):
            rows(character)
        character = self.character()
        character["active_build_index"] = 99
        with self.assertRaises(ValueError):
            rows(character)
        with self.assertRaises(ValueError):
            change_packet(self.character(), dict(self.character(), account_id=99))
