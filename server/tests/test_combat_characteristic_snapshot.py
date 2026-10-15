"""Focused tests for native position-free characteristic snapshot projection."""

import struct
import unittest

from wakfu_server.combat.combat_characteristic_snapshot import (
    characteristics_only_snapshot,
)


class CharacteristicSnapshotProjectionTests(unittest.TestCase):
    @staticmethod
    def full_snapshot(kind, rows):
        # The actor metadata preceding the native characteristic table differs
        # for player (format 3) and NPC/summon (format 2).
        prefix = bytes((kind,))
        if kind == 3:
            prefix += struct.pack(">q", 0x102030405060708)
        prefix += struct.pack(">iihqBB", -22, 7, 312, 0x102030405060, 1, 2)
        prefix += struct.pack(">iBBBBbB", 1189, 3, 4, 5, 6, -1, 7)
        return prefix + struct.pack(">H", len(rows)) + b"".join(rows)

    @staticmethod
    def row(identity, current, minimum, maximum, percentage=0):
        return struct.pack(">Biiii", identity, current, minimum, maximum, percentage)

    def test_player_npc_and_summon_project_exact_characteristic_bytes(self):
        rows = b"".join(
            (
                self.row(1, 321, 0, 654, 17),
                self.row(29, -7, -100, 100, -25),
                self.row(95, 3, 0, 12, 0),
            )
        )
        for kind in (2, 3):
            with self.subTest(format=kind):
                full = self.full_snapshot(
                    kind,
                    [
                        self.row(1, 321, 0, 654, 17),
                        self.row(29, -7, -100, 100, -25),
                        self.row(95, 3, 0, 12, 0),
                    ],
                )
                projected = characteristics_only_snapshot(full)
                self.assertEqual(projected, bytes((40,)) + struct.pack(">H", 3) + rows)
                self.assertNotIn(struct.pack(">i", 1189), projected)

    def test_rejects_missing_unsupported_and_truncated_snapshots(self):
        for invalid in (b"", None, bytearray(b"\x02"), b"\x01" + b"\0" * 64):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(ValueError):
                    characteristics_only_snapshot(invalid)

        valid_empty_table = self.full_snapshot(2, [])
        for invalid in (
            valid_empty_table[:-1],
            valid_empty_table[:-2] + b"\x00\x01",
            valid_empty_table[:-2] + b"\x00\x01" + b"\x01\x00\x00",
        ):
            with self.subTest(length=len(invalid)):
                with self.assertRaises(ValueError):
                    characteristics_only_snapshot(invalid)

    def test_does_not_emit_actor_position_or_trailing_full_snapshot_fields(self):
        rows = [self.row(1, 55, 2, 99, -3)]
        full = self.full_snapshot(3, rows) + b"position-or-other-metadata"
        projected = characteristics_only_snapshot(full)
        self.assertEqual(projected, b"\x28\x00\x01" + rows[0])
        self.assertNotIn(b"position-or-other-metadata", projected)


if __name__ == "__main__":
    unittest.main()
