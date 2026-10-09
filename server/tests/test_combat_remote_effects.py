import struct
import unittest

from wakfu_server.combat_remote_effects import (
    RemoteRunningEffect,
    decode_remote_effects,
    encode_remote_effects,
)


class RemoteEffectTests(unittest.TestCase):
    def test_state_carrier_and_grant_order_and_payload_are_preserved(self):
        records = (
            RemoteRunningEffect(310, b"state"),
            RemoteRunningEffect(649, b"grant", 125),
        )
        expected = (
            b"\x00\x02"
            + struct.pack(">ih", 310, 5)
            + b"state"
            + bytes(4)
            + struct.pack(">ih", 649, 5)
            + b"grant"
            + struct.pack(">i", 125)
        )
        self.assertEqual(encode_remote_effects(records), expected)
        self.assertEqual(decode_remote_effects(expected), records)

    def test_native_oversize_fallback_is_empty_population(self):
        records = (RemoteRunningEffect(649, bytes(25000)),) * 2
        self.assertEqual(encode_remote_effects(records), bytes(2))

    def test_truncated_negative_and_trailing_envelopes_are_rejected(self):
        for body in (
            b"",
            b"\xff\xff",
            b"\x00\x01",
            b"\x00\x00x",
            b"\x00\x01" + struct.pack(">ih", 649, -1),
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                decode_remote_effects(body)

    def test_codec_requires_attested_typed_records(self):
        with self.assertRaises(ValueError):
            encode_remote_effects((dict(effect_class=649, payload=b""),))
        with self.assertRaises(ValueError):
            RemoteRunningEffect(649, b"", 1 << 31)


if __name__ == "__main__":
    unittest.main()
