"""Focused native binding publication and legacy chest projection checks."""
import unittest

from wakfu_server import item_binding
from wakfu_server.exchange_rules import ITEMS
from wakfu_server.haven_chest import _identity, _move


def _read_varint(data, offset):
    value = shift = 0
    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7


def _fields(data):
    rows = []
    offset = 0
    while offset < len(data):
        key, offset = _read_varint(data, offset)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, offset = _read_varint(data, offset)
        elif wire == 2:
            length, offset = _read_varint(data, offset)
            value, offset = data[offset : offset + length], offset + length
        else:
            raise AssertionError(f"unexpected wire type {wire}")
        rows.append((number, wire, value))
    return rows


class ItemBindingPublicationTests(unittest.TestCase):
    def test_native_binding_field_is_nested_message_and_binary_option_matches(self):
        binding_type = ITEMS["33214"]["binding_template"]["id"]
        item = {"uid": 17, "reference": 33214, "bound": True}
        outer = _fields(item_binding.proto(item))
        self.assertEqual(len(outer), 1)
        self.assertEqual(outer[0][:2], (55, 2))
        self.assertEqual(_fields(outer[0][2]), [(1, 0, binding_type), (2, 0, 1)])
        self.assertEqual(item_binding.binary_option(item), bytes((1, binding_type, 1)))

    def test_unbound_template_and_unbound_item_emit_no_binding_extension(self):
        item = {"uid": 18, "reference": 20595}
        self.assertEqual(item_binding.proto(item), b"")
        self.assertEqual(item_binding.binary_option(item), b"\x00")
        self.assertEqual(item_binding.proto(dict(item, bound=False)), b"")

    def test_historical_chest_binding_sidecar_projects_without_mutating_entry(self):
        item = {"uid": 19, "reference": 20595, "quantity": 1}
        metadata = {
            "inventory_item_bindings": {
                "uid": 19,
                "bound": True,
                "template_reference": 20595,
            },
            "inventory_item_shards": {"uid": 19, "shard_state": b"\x18\x01"},
        }
        projected = item_binding.from_custody(item, metadata)
        self.assertTrue(projected["bound"])
        self.assertEqual(
            projected["binding_type"], ITEMS["20595"]["binding_template"]["id"]
        )
        self.assertNotIn("bound", item)
        self.assertEqual(metadata["inventory_item_shards"]["shard_state"], b"\x18\x01")
        self.assertEqual(_fields(item_binding.proto(projected))[0][:2], (55, 2))

    def test_historical_and_hydrated_chest_rows_merge_only_with_same_binding_authority(
        self,
    ):
        sidecar = {
            "inventory_item_bindings": {
                "uid": 31,
                "bound": True,
                "template_reference": 20595,
            }
        }
        historical = {
            "item": {"uid": 31, "reference": 20595, "quantity": 1, "slot": 0},
            "metadata": sidecar,
        }
        current_item = item_binding.from_custody(
            {"uid": 32, "reference": 20595, "quantity": 1, "slot": 1},
            {
                "inventory_item_bindings": {
                    "uid": 32,
                    "bound": True,
                    "template_reference": 20595,
                }
            },
        )
        current = {
            "item": current_item,
            "metadata": {
                "inventory_item_bindings": {
                    "uid": 32,
                    "bound": True,
                    "template_reference": 20595,
                }
            },
        }
        self.assertEqual(_identity(historical), _identity(current))
        different_binding = {
            "item": {
                "uid": 33,
                "reference": 20595,
                "quantity": 1,
                "slot": 2,
                "bound": False,
                "binding_type": current_item["binding_type"],
            },
            "metadata": {
                "inventory_item_bindings": {
                    "uid": 33,
                    "bound": False,
                    "template_reference": 20595,
                }
            },
        }
        self.assertNotEqual(_identity(historical), _identity(different_binding))

        _move(historical, current, 1, 99, lambda: 40)
        self.assertEqual(current["item"]["quantity"], 2)
        self.assertEqual(historical["item"]["quantity"], 0)

    def test_custody_projection_requires_matching_uid_reference_and_boolean(self):
        item = {"uid": 20, "reference": 20595}
        for row in (
            {"uid": 21, "bound": True, "template_reference": 20595},
            {"uid": 20, "bound": True, "template_reference": 2504},
            {"uid": 20, "bound": 1, "template_reference": 20595},
        ):
            with self.subTest(row=row), self.assertRaises(ValueError):
                item_binding.from_custody(item, {"inventory_item_bindings": row})

    def test_explicit_binding_type_and_flag_are_strictly_validated(self):
        for item in (
            {"uid": 1, "reference": 20595, "bound": 1},
            {"uid": 1, "reference": 20595, "binding_type": True, "bound": True},
            {"uid": 1, "reference": 20595, "binding_type": 128, "bound": True},
        ):
            with self.subTest(item=item), self.assertRaises(ValueError):
                item_binding.proto(item)


if __name__ == "__main__":
    unittest.main(verbosity=2)
