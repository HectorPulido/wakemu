import struct
import unittest

from wakfu_server.shard_identification_wire import response
from wakfu_server.wire import proto_field


class ShardIdentificationWireTests(unittest.TestCase):
    def test_success_preserves_both_native_blobs(self):
        shard = proto_field(
            10, proto_field(80, 0) + proto_field(96, 1) + proto_field(88, 0)
        )
        self.assertEqual(
            response(dict(uid=31, status=0, elements=b"\x1a\x00", shard_state=shard)),
            (
                13766,
                struct.pack(">iqBI", 0, 31, 0, 2)
                + b"\x1a\x00"
                + struct.pack(">I", len(shard))
                + shard,
            ),
        )

    def test_level_rejection_has_no_socket_replacement(self):
        self.assertEqual(
            response(dict(uid=31, status=2, shard_state=None)),
            (13766, struct.pack(">iqBII", 2, 31, 0, 0, 0)),
        )

    def test_invalid_results_cannot_emit_success_or_invalid_masks(self):
        for result in (
            dict(uid=31, status=0),
            dict(uid=31, status=1),
            dict(uid=True, status=2),
            dict(uid=31, status=True),
            dict(uid=31, status=2, elements=b"\x01\x00"),
            dict(uid=31, status=2, elements=b"\x00"),
        ):
            with self.assertRaises(ValueError):
                response(result)
