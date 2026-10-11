"""Native shared storage request semantics and guild snapshot boundaries."""
import struct
import unittest
from unittest.mock import patch

from wakfu_server.characters import guild_chest_wire as wire
from wakfu_server.characters.guild_wire import decode_storage_request


class GuildChestWireTests(unittest.TestCase):
    def chest(self, identity=0):
        return dict(id=identity, capacity=40, items=[])

    def test_deposit_reference_and_quantity_are_distinct_native_fields(self):
        body = struct.pack(">ibqihb", 0, 0, 99, 16942, 7, 3)
        self.assertEqual(
            decode_storage_request(12531, body),
            dict(
                compartment_id=0,
                operation=0,
                item_id=99,
                reference=16942,
                quantity=7,
                slot=3,
            ),
        )

    def test_withdrawal_contains_destination_container_and_quantity(self):
        body = struct.pack(">ibqihqb", 0, 1, 99, 16942, 7, 800, 5)
        self.assertEqual(
            decode_storage_request(12531, body),
            dict(
                compartment_id=0,
                operation=1,
                item_id=99,
                reference=16942,
                quantity=7,
                additional_item_id=800,
                slot=5,
            ),
        )
        with self.assertRaises(ValueError):
            decode_storage_request(12531, body + b"\x00")

    def test_native_enabled_map_and_treasury_layout(self):
        chests = [self.chest(i) for i in range(4)]
        chests[3]["enabled"] = False
        opcode, body = wire.bootstrap(chests, 1234)
        self.assertEqual(opcode, 14424)
        self.assertEqual(
            body,
            bytes.fromhex(
                "00000004 0000000001 0000000101 0000000201 0000000300 00000000000004d2"
            ),
        )
        self.assertEqual(wire.money_packet(1234), (15817, struct.pack(">qi", 1234, 0)))

    def test_empty_snapshot_contains_required_history_and_compartment_fields(self):
        self.assertEqual(
            wire.contents([self.chest()]), (14787, bytes.fromhex("0a0408001001 1200"))
        )

    def test_only_native_guild_ids_and_capacity_are_accepted(self):
        for chest in [
            self.chest(4),
            dict(id=True),
            dict(id=0, capacity=80),
            dict(id=0, enabled=1),
        ]:
            with self.subTest(chest=chest), self.assertRaises(ValueError):
                wire.bootstrap([chest])
        with self.assertRaises(ValueError):
            wire.contents([self.chest(), self.chest()])

    def test_item_slot_bounds_duplicates_and_disabled_compartments(self):
        with patch.object(wire, "item_proto", return_value=b"\x08\x63\x10\x01\x18\x01"):
            for slot in [-1, 40, True]:
                chest = self.chest()
                chest["items"] = [dict(slot=slot, item=dict(uid=99))]
                with self.subTest(slot=slot), self.assertRaises(ValueError):
                    wire.contents([chest])
            chest = self.chest()
            chest["items"] = [
                dict(slot=0, item=dict(uid=99)),
                dict(slot=1, item=dict(uid=99)),
            ]
            with self.assertRaises(ValueError):
                wire.contents([chest])
            chest["items"] = chest["items"][:1]
            chest["enabled"] = False
            with self.assertRaises(ValueError):
                wire.contents([chest])

    def test_money_and_actor_bounds_reject_unsigned_overflow(self):
        for amount in [-1, 1 << 63, True]:
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                wire.money_packet(amount)
        for actor in [0, -1, 1 << 63, True]:
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                wire.open_packet(actor)
