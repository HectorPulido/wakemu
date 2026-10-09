import struct
import unittest

from wakfu_server.proto_dungeon import decode, encode
from wakfu_server.native_transports import bootstrap


FIXTURE = bytes.fromhex("08641003180120002800300038b9604055")
CONTEXT = {
    "max_level": 100,
    "difficulty_level": 3,
    "is_difficulty_available": True,
    "can_increase_difficulty": False,
    "is_fight_in_progress": False,
    "is_competitive_cancelled": False,
    "allowed_ids": [12345],
    "min_level": 85,
}


class ProtoDungeonTests(unittest.TestCase):
    def test_native_fixture_roundtrips(self):
        self.assertEqual(encode(CONTEXT), FIXTURE)
        self.assertEqual(decode(FIXTURE), dict(CONTEXT, allowed_ids=(12345,)))
        signed = dict(CONTEXT, allowed_ids=[-(1 << 63), (1 << 63) - 1])
        self.assertEqual(
            decode(encode(signed))["allowed_ids"], tuple(signed["allowed_ids"])
        )

    def test_bootstrap_accepts_explicit_context_and_keeps_default(self):
        character = {
            "id": 7,
            "account_id": 9,
            "map_id": 1086,
            "instance_id": 0,
            "x": 1,
            "y": 2,
            "z": -1,
        }
        normal = bootstrap(character)
        contextual = bootstrap(character, dungeon_context=CONTEXT)
        self.assertEqual(
            normal[1][1].endswith(bytes.fromhex("0800100218002001280030004000")), True
        )
        body = contextual[1][1]
        offset = 0
        blocks = []
        while offset < len(body):
            length = struct.unpack_from(">H", body, offset)[0]
            offset += 2
            blocks.append(body[offset : offset + length])
            offset += length
        self.assertEqual(decode(blocks[3]), dict(CONTEXT, allowed_ids=(12345,)))

    def test_rejects_invalid_types_and_ranges(self):
        for change in (
            {"difficulty_level": 0},
            {"difficulty_level": 11},
            {"max_level": True},
            {"can_increase_difficulty": 1},
            {"allowed_ids": [-(1 << 63) - 1]},
            {"allowed_ids": [1 << 63]},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                encode(dict(CONTEXT, **change))

    def test_rejects_truncated_and_out_of_range_wire_values(self):
        with self.assertRaises(ValueError):
            decode(bytes.fromhex("08"))
        with self.assertRaises(ValueError):
            decode(bytes.fromhex("1080"))

    def test_rejects_overflowing_varints_in_boolean_and_unknown_fields(self):
        overflow = b"\xff" * 9 + b"\x02"
        for tag in (b"\x18", b"\x48"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                decode(tag + overflow)


if __name__ == "__main__":
    unittest.main()
