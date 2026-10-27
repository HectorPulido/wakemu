"""Native chat configuration uses the original cEp22318 key/value protocol."""
import struct
import unittest

from protocol_codec import Reader
from wakfu_server import wire


class NativeChatFloodTests(unittest.TestCase):
    def test_text_flood_override_is_one_native_key_and_preserves_xp_wire(self):
        opcode, body = wire.native_chat_flood_packet()
        self.assertEqual(opcode, 22318)
        reader = Reader(body)
        self.assertEqual(reader.take(reader.number("I")), b"chat.flood.check.enabled")
        self.assertEqual(reader.take(reader.number("I")), b"false")
        reader.finish()
        self.assertEqual(
            wire.native_configuration_packet("base.xp.ratio", "10"),
            wire.native_xp_rate_packet(100000),
        )
        self.assertEqual(
            wire.native_configuration_packet("private.probe", "á"),
            (
                22318,
                struct.pack(">I", 13)
                + b"private.probe"
                + struct.pack(">I", 2)
                + "á".encode(),
            ),
        )
        for key, value in (
            (None, "false"),
            ("", "false"),
            ("a\x00b", "false"),
            ("key", False),
            ("key", "\x00"),
            ("x" * 257, "false"),
            ("key", "x" * 65537),
        ):
            with self.subTest(
                key_type=type(key).__name__, value_type=type(value).__name__
            ):
                with self.assertRaises(ValueError):
                    wire.native_configuration_packet(key, value)


if __name__ == "__main__":
    unittest.main()
