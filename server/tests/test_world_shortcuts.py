import struct
import unittest
import hashlib
from unittest.mock import patch

from wakfu_server import world_shortcuts
from wakfu_server import wire


class WorldShortcutCodecTests(unittest.TestCase):
    def test_native_12091_java_probe_fixture_decodes_and_roundtrips(self):
        # Byte layout asserted by the offline cnE/bOS/fyt/yu Java probe:
        # actor, one removal key, one assignment key, then a type-1 descriptor.
        native_body = bytes.fromhex(
            "0000000000003039"  # character 12345
            "0001 00010203"  # remove WORLD bar 1, slot 3
            "0001 00010204"  # assign WORLD bar 1, slot 4
            "01 00000000000010b3 000010b3 ffffffff"  # reference 4275
        )
        self.assertEqual(len(native_body), 37)
        decoded = world_shortcuts.decode(native_body)
        self.assertEqual(
            decoded,
            {
                "actor_id": 12345,
                "removals": [(1, 2, 3)],
                "assignments": {
                    (1, 2, 4): {
                        "shortcut_type": 1,
                        "long_value": 4275,
                        "int_value": 4275,
                        "extra_int": -1,
                    }
                },
            },
        )
        assignment = decoded["assignments"][(1, 2, 4)]
        rebuilt = (
            struct.pack(">qh", decoded["actor_id"], len(decoded["removals"]))
            + struct.pack(">i", 0x010203)
            + struct.pack(">h", len(decoded["assignments"]))
            + struct.pack(">i", 0x010204)
            + world_shortcuts.DESCRIPTOR.pack(
                assignment["shortcut_type"],
                assignment["long_value"],
                assignment["int_value"],
                assignment["extra_int"],
            )
        )
        self.assertEqual(rebuilt, native_body)

    def test_decode_finishes_entire_native_delta_before_returning(self):
        valid = bytes.fromhex(
            "0000000000003039 0000 0001 00010204"
            "02 000000003ade68b1 000010b3 ffffffff"
        )
        decoded = world_shortcuts.decode(valid)
        self.assertEqual(decoded["assignments"][(1, 2, 4)]["shortcut_type"], 2)
        self.assertEqual(decoded["assignments"][(1, 2, 4)]["long_value"], 987654321)
        for end in range(len(valid)):
            with self.subTest(truncated_at=end), self.assertRaises(ValueError):
                world_shortcuts.decode(valid[:end])
        with self.assertRaisesRegex(ValueError, "undecoded bytes"):
            world_shortcuts.decode(valid + b"\0")

    def test_native_count_limits_and_identity_are_validated(self):
        for actor in (0, -1):
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                world_shortcuts.decode(
                    struct.pack(">qh", actor, 0) + struct.pack(">h", 0)
                )
        for count in (-1, world_shortcuts.MAX_POSITIONS * 2 + 1):
            with self.subTest(removal_count=count), self.assertRaises(ValueError):
                world_shortcuts.decode(
                    struct.pack(">qh", 1, count) + struct.pack(">h", 0)
                )
        for count in (-1, world_shortcuts.MAX_POSITIONS + 1):
            with self.subTest(assignment_count=count), self.assertRaises(ValueError):
                world_shortcuts.decode(
                    struct.pack(">qh", 1, 0) + struct.pack(">h", count)
                )

    def test_world_coordinate_keys_reject_invalid_bar_slot_and_type(self):
        for key in (-1, 0x000008, 0x040000, 0x030000):
            with self.subTest(key=key), self.assertRaises(ValueError):
                world_shortcuts.coordinate(key)
        self.assertEqual(world_shortcuts.coordinate(0x010000), (1, 0, 0))
        self.assertEqual(world_shortcuts.coordinate(0x020000), (2, 0, 0))

    def test_duplicate_removals_are_idempotent_but_duplicate_assignments_fail(self):
        key = 0x010203
        descriptor = world_shortcuts.DESCRIPTOR.pack(1, 4275, 4275, -1)
        removals = struct.pack(">qhii h", 1, 2, key, key, 0)
        decoded = world_shortcuts.decode(removals)
        self.assertEqual(decoded["removals"], [(1, 2, 3)])

        duplicate_assignments = (
            struct.pack(">qh", 1, 0)
            + struct.pack(">h", 2)
            + struct.pack(">i", key)
            + descriptor
            + struct.pack(">i", key)
            + descriptor
        )
        with self.assertRaisesRegex(ValueError, "Duplicate shortcut assignment"):
            world_shortcuts.decode(duplicate_assignments)

    def test_removal_and_assignment_for_same_coordinate_is_a_replacement(self):
        key = 0x010203
        body = (
            struct.pack(">qh", 1, 1)
            + struct.pack(">i", key)
            + struct.pack(">h", 1)
            + struct.pack(">i", key)
            + world_shortcuts.DESCRIPTOR.pack(2, 987654321, 4275, -1)
        )
        decoded = world_shortcuts.decode(body)
        self.assertEqual(decoded["removals"], [(1, 2, 3)])
        self.assertEqual(decoded["assignments"][(1, 2, 3)]["long_value"], 987654321)

    def test_non_world_domains_decode_without_applying_world_bar_limits(self):
        keys = (0x010000, 0x020000)
        body = (
            struct.pack(">qh", 9, 2) + struct.pack(">ii", *keys) + struct.pack(">h", 0)
        )
        decoded = world_shortcuts.decode(body)
        self.assertEqual(decoded["removals"], [(1, 0, 0), (2, 0, 0)])

    def test_world_collection_matches_native_wire_shape_and_sorts_slots(self):
        entries = [
            {
                "bar_number": 2,
                "slot": 3,
                "shortcut_type": 1,
                "long_value": 4275,
                "int_value": 4275,
                "extra_int": -1,
            },
            {
                "bar_number": 2,
                "slot": 1,
                "shortcut_type": 2,
                "long_value": 987654321,
                "int_value": 4275,
                "extra_int": -1,
            },
        ]
        wire = world_shortcuts.collection(entries)
        # Four native bars: two empty predecessors, then ordered slots 1 and 3,
        # and an empty final bar. This also pins the Java yu descriptor layout.
        expected = (
            struct.pack(">H", 4)
            + struct.pack(">bH", 0, 0) * 2
            + struct.pack(">bH", 0, 2)
            + struct.pack(">h", 1)
            + world_shortcuts.DESCRIPTOR.pack(2, 987654321, 4275, -1)
            + struct.pack(">h", 3)
            + world_shortcuts.DESCRIPTOR.pack(1, 4275, 4275, -1)
            + struct.pack(">bH", 0, 0)
        )
        self.assertEqual(wire, expected)
        self.assertEqual(len(world_shortcuts.collection([])), 14)

    def test_collection_rejects_duplicate_unsupported_and_out_of_range_entries(self):
        base = {
            "bar_number": 0,
            "slot": 0,
            "shortcut_type": 1,
            "long_value": 1,
            "int_value": 1,
            "extra_int": -1,
        }
        for bar, slot in ((-1, 0), (4, 0), (0, -1), (0, 8), (0, 256)):
            entry = dict(base, bar_number=bar, slot=slot)
            with self.subTest(bar=bar, slot=slot), self.assertRaises(ValueError):
                world_shortcuts.collection([entry])
        with self.assertRaises(ValueError):
            world_shortcuts.collection([base, dict(base)])
        with self.assertRaises(ValueError):
            world_shortcuts.collection([dict(base, shortcut_type=3)])

    def test_minimal_entity_inserts_owned_world_collection_at_shortcut_section(self):
        body = b"\x0bfixture-prefixold-shortcutsfixture-suffix"
        start = len(b"\x0bfixture-prefix")
        end = start + len(b"old-shortcuts")
        layout = {
            "template_sha256": hashlib.sha256(body).hexdigest(),
            "sections": [
                {
                    "name": "SHORTCUT_INVENTORIES",
                    "start": start,
                    "end": end,
                }
            ],
        }
        character = {
            "level": 1,
            "world_shortcuts": [
                {
                    "bar_number": 1,
                    "slot": 2,
                    "shortcut_type": 1,
                    "long_value": 4275,
                    "int_value": 4275,
                    "extra_int": -1,
                }
            ],
            "inventory_items": [],
        }
        with patch.dict(wire.ENTITY_LAYOUTS, {11: layout}):
            result = wire.minimal_entity(body, character)
        expected = world_shortcuts.collection(character["world_shortcuts"])
        self.assertEqual(result, body[:start] + expected + body[end:])


if __name__ == "__main__":
    unittest.main()
