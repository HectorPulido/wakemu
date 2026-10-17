"""Exact native cvM envelope and fail-closed external member identities."""
import struct
import unittest

from wakfu_server.combat_multiplayer_wire import removed, decode_removed


class ExternalMemberRemovalCodecTests(unittest.TestCase):
    def test_exact_native_constructor_header_and_signed_actor_identity(self):
        # Original cvM reader + aUK callback receipt native-removal-v4:
        # packet SHA69a896759d5d35303cf87b47f6883af9e0192e4e1cabd4530a134a39433bee6d.
        self.assertEqual(
            removed(226, 31, action_id=0, action_context=-1),
            (12347, bytes.fromhex("000000e200000000ffffffff000000000000001f")),
        )
        for actor_id in (31, -1125900015052032):
            with self.subTest(actor_id=actor_id):
                packet = removed(226, actor_id, action_id=0, action_context=-1)
                self.assertEqual(
                    packet, (12347, struct.pack(">iiiq", 226, 0, -1, actor_id))
                )
                self.assertEqual(len(packet[1]), 20)
                self.assertEqual(
                    decode_removed(packet[1]),
                    dict(
                        fight_id=226, action_id=0, action_context=-1, actor_id=actor_id
                    ),
                )

    def test_header_requires_explicit_context_and_preserves_supplied_values(self):
        with self.assertRaises(TypeError):
            removed(226, 31)
        packet = removed(226, 31, action_id=17, action_context=-9)
        self.assertEqual(decode_removed(packet[1])["action_id"], 17)
        self.assertEqual(decode_removed(packet[1])["action_context"], -9)

    def test_invalid_identity_types_ranges_and_lengths_are_rejected(self):
        for keyword, value in (
            ("fight_id", True),
            ("fight_id", 0),
            ("fight_id", 2**31),
            ("actor_id", True),
            ("actor_id", 0),
            ("actor_id", 2**63),
            ("action_id", False),
            ("action_id", 2**31),
            ("action_context", None),
            ("action_context", -(2**31) - 1),
        ):
            with self.subTest(keyword=keyword, value=value):
                arguments = dict(
                    fight_id=226, actor_id=31, action_id=0, action_context=-1
                )
                arguments[keyword] = value
                with self.assertRaises(ValueError):
                    removed(**arguments)
        body = removed(226, 31, action_id=0, action_context=-1)[1]
        for malformed in (
            body[:-1],
            body + b"x",
            bytearray(body),
            struct.pack(">iiiq", 226, 0, -1, 0),
        ):
            with self.subTest(malformed=type(malformed).__name__):
                with self.assertRaises(ValueError):
                    decode_removed(malformed)
