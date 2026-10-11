import struct
import unittest
from wakfu_server.maps.npc_capture_scene import scope_reference_actors


class CapturedNpcSceneTests(unittest.TestCase):
    def packet(self, map_id=1134, inner=-77):
        blob = b"\x0b" + struct.pack(">qBqH", inner, 1, -1, 4) + b"Wuan"
        blob += struct.pack(">hiihq", 4800, -17, 9, -1, map_id)
        npc = struct.pack(">BqH", 1, -77, len(blob)) + blob
        player = struct.pack(">BqH", 0, 10, 1) + b"\x01"
        return b"\x00\x02" + player + npc

    def test_keeps_native_npc_only_in_matching_public_scene(self):
        original = self.packet()
        self.assertEqual(scope_reference_actors(original, 1134, 0)[1], 1)
        self.assertEqual(scope_reference_actors(original, 1387, 0), b"\x00\x00")
        self.assertEqual(scope_reference_actors(original, 1134, 5), b"\x00\x00")

    def test_rejects_malformed_capture_and_envelope_identity(self):
        original = self.packet()
        for packet in (b"", original[:-1], original + b"x", self.packet(inner=-78)):
            with self.assertRaises(ValueError):
                scope_reference_actors(packet, 1134, 0)

    def test_preserves_other_native_formats_without_inventing_position_layout(self):
        opaque = b"\x05\xaa"
        packet = b"\x00\x01" + struct.pack(">BqH", 1, -88, len(opaque)) + opaque
        self.assertEqual(scope_reference_actors(packet, 1387, 0), packet)

    def test_registry_owns_enabled_and_quarantined_identities_exclusively(self):
        self.assertEqual(
            scope_reference_actors(self.packet(), 1134, 0, [-77]), b"\x00\x00"
        )
        self.assertEqual(scope_reference_actors(self.packet(), 1134, 0, [-88])[1], 1)
