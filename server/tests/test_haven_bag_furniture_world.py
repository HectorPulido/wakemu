"""Dynamic furniture entities carry native ownership and instance identities."""
import struct
import unittest
from unittest.mock import patch
from wakfu_server import haven_bag_furniture_world as world


class FurnitureWorldTests(unittest.TestCase):
    def setUp(self):
        self.item = dict(
            item_ref=6293,
            template_id=2770,
            item_uid=1099511633800,
            x=1,
            y=10,
            z=0,
            direction=3,
            virtual=True,
            deployed=True,
        )
        self.character = {"id": 1, "haven_bag": {"furniture": [self.item]}}
        self.definition = {"template_id": 2770, "kind": "Decoration"}
        self.mock = patch.object(world, "resolve_item", return_value=self.definition)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def test_dynamic_record_separates_instance_template_and_owner(self):
        opcode, body = world.upsert(self.character, self.item)
        self.assertEqual(opcode, 13664)
        self.assertEqual(
            struct.unpack_from(">hqqH", body), (1, 1099511633800, 2770, 31)
        )
        blob = body[20:51]
        self.assertEqual(blob[:7], struct.pack(">BBIB", 1, 3, 6, 0))
        self.assertEqual(
            struct.unpack(">iihBq?i", blob[7:]), (1, 10, 0, 3, 1, True, 6293)
        )
        packed = struct.unpack(">q", body[51:])[0]
        self.assertEqual(
            (
                (packed >> 28 & 262143) - 131071,
                (packed >> 10 & 262143) - 131071,
                (packed & 1023) - 511,
            ),
            (1, 10, 0),
        )

    def test_craft_subtype_has_no_decoration_tail(self):
        self.definition["kind"] = "PortableCraftTable"
        _, body = world.upsert(self.character, self.item)
        self.assertEqual(struct.unpack_from(">H", body, 18)[0], 27)
        self.assertEqual(len(body), 55)

    def test_packed_units_are_not_rendered_and_removal_uses_instance(self):
        self.item["deployed"] = False
        self.assertEqual(world.packets(self.character), [])
        self.assertEqual(
            world.remove(self.item), (13082, struct.pack(">hq", 1, 1099511633800))
        )
        with self.assertRaises(ValueError):
            world.upsert(self.character, self.item)

    def test_mapping_mismatch_and_invalid_positions_fail_closed(self):
        self.definition["template_id"] = 999
        with self.assertRaises(ValueError):
            world.upsert(self.character, self.item)
        self.definition["template_id"] = 2770
        self.item["x"] = 18
        with self.assertRaises(ValueError):
            world.upsert(self.character, self.item)
