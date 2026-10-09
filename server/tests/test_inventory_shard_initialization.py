import unittest

from wakfu_server.inventory_shards import initialized_wire_state, legacy_option
from wakfu_server.items.inventory_items import item_proto
from wakfu_server.wire import proto_field, proto_fields


class NativeShardInitializationTests(unittest.TestCase):
    def test_legacy_empty_socket_gets_required_reference_without_equipment_loss(self):
        slot = proto_field(80, 0) + proto_field(96, 3)
        original = proto_field(10, slot) + proto_field(800, 19)
        initialized = initialized_wire_state(original)
        fields = dict(proto_fields(initialized))
        self.assertEqual(dict(proto_fields(fields[10])), {80: 0, 96: 3, 88: 0})
        self.assertEqual(fields[800], 19)
        self.assertEqual(legacy_option(original), legacy_option(initialized))
        item = dict(uid=123, reference=2024, quantity=1, shard_state=original)
        encoded = dict(proto_fields(item_proto(item)))
        self.assertEqual((encoded[8], encoded[16], encoded[24]), (123, 2024, 1))
        self.assertEqual(encoded[418], initialized)
        self.assertEqual(item["shard_state"], original)

    def test_complete_occupied_slot_is_byte_exact(self):
        original = proto_field(
            10, proto_field(80, 1) + proto_field(88, 1234) + proto_field(112, 2)
        )
        self.assertEqual(initialized_wire_state(original), original)

    def test_unknown_occupied_reference_and_missing_position_are_rejected(self):
        for slot in (proto_field(80, 1) + proto_field(112, 2), proto_field(88, 0)):
            with self.subTest(slot=slot), self.assertRaises(ValueError):
                initialized_wire_state(proto_field(10, slot))
