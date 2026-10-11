from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from decode_native_interactive_activation_cells import decode


class NativeActivationCellsTests(unittest.TestCase):
    def record(self):
        payload = bytes.fromhex(
            "02000000000b010000000d000001012dfffffffeffffffbf0000000101010100000003fffffffdffffffbd0000fffffff8ffffffc5000000000009ffffffc50000000000000000000000"
        )
        return dict(map_id=301, x=-2, y=-65, z=0, payload_hex=payload.hex())

    def test_literal_riktus_activation_points_differ_from_center(self):
        self.assertEqual(
            decode(self.record()), [[-3, -67, 0], [-8, -59, 0], [9, -59, 0]]
        )

    def test_rejects_truncated_points(self):
        record = self.record()
        record["payload_hex"] = record["payload_hex"][:90]
        with self.assertRaises(ValueError):
            decode(record)

    def test_rejects_wrong_identity(self):
        record = self.record()
        record["map_id"] = 302
        with self.assertRaises(ValueError):
            decode(record)

    def test_rejects_ambiguous_content_frame(self):
        record = self.record()
        record["payload_hex"] += struct.pack(">hiih", 301, -2, -65, 0).hex()
        with self.assertRaises(ValueError):
            decode(record)
