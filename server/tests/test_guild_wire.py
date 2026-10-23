"""Offline regression tests for native guild packet and snapshot codecs."""
import struct
import unittest

from wakfu_server.company_authority import CompanySnapshot

from wakfu_server.characters import guild_wire
from wakfu_server.characters import hero_wire, social


def _i32_text(text):
    payload = text.encode("utf-8")
    return struct.pack(">i", len(payload)) + payload


def _varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def _guild_model():
    return {
        "guildId": 456,
        "level": 3,
        "blazon": 0x10000000007,
        "name": "Gremio ñ",
        "description": "Descripción",
        "message": "Bienvenidos",
        "currentGuildPoints": 12,
        "totalGuildPoints": 345,
        "weeklyPointsLimit": 500,
        "earnedPointsLimit": 80,
        "lastEarningPointWeek": 202640,
        "ranks": [
            {"id": 9, "name": "Líder", "authorizations": (1 << 40) + 7, "position": 0},
            {"id": 10, "name": "Recluta", "authorizations": 0, "position": 1},
        ],
        "members": [
            {
                "id": 900,
                "ownerId": (1 << 40) + 2,
                "guildPoints": 17,
                "rank": 9,
                "xp": 123456,
                "isConnected": True,
                "smiley": b"\x01",
                "sex": b"\x00",
                "breedId": 7,
                "nationId": 2,
                "name": "Héctor",
                "saveDate": 1729000000,
                "serializedLanguages": b"\x00",
                "accountCommunityId": b"\x01",
            }
        ],
        "bonuses": [],
    }


class GuildWireTests(unittest.TestCase):
    def test_guild_chat_decodes_unicode_and_full_signed_i64_identity(self):
        guild_id = 0x0001000000000007
        text = "Prueba ñ 🌱"
        encoded = text.encode("utf-8")
        body = struct.pack(">qH", guild_id, len(encoded)) + encoded

        self.assertEqual(
            {"guild_id": guild_id, "text": text},
            guild_wire.decode_request(13744, body),
        )
        self.assertEqual(
            {"guild_id": -1, "text": "Prueba ñ"},
            guild_wire.decode_request(
                13744,
                struct.pack(">qH", -1, len("Prueba ñ".encode())) + "Prueba ñ".encode(),
            ),
        )

    def test_guild_chat_rejects_each_truncation_boundary(self):
        body = struct.pack(">qH", 456, 3) + b"abc"
        for truncated in (body[:0], body[:7], body[:8], body[:9], body[:10], body[:-1]):
            with self.subTest(length=len(truncated)):
                with self.assertRaises(ValueError):
                    guild_wire.decode_request(13744, truncated)

    def test_guild_chat_rejects_trailing_bytes_and_invalid_utf8(self):
        with self.assertRaisesRegex(ValueError, "undecoded"):
            guild_wire.decode_request(13744, struct.pack(">qH", 456, 1) + b"x!")
        with self.assertRaises(UnicodeDecodeError):
            guild_wire.decode_request(13744, struct.pack(">qH", 456, 1) + b"\xff")

    def test_creation_and_rank_requests_decode_native_layouts(self):
        self.assertEqual(
            {
                "blazon": (1 << 40) + 123,
                "name": "Gremio ñ",
                "best_rank_name": "Líder",
                "worst_rank_name": "Recluta",
            },
            guild_wire.decode_request(
                13757,
                struct.pack(">q", (1 << 40) + 123)
                + _i32_text("Gremio ñ")
                + _i32_text("Líder")
                + _i32_text("Recluta"),
            ),
        )
        self.assertEqual(
            {"name": "Élite", "authorizations": (1 << 45) + 3},
            guild_wire.decode_request(
                15194,
                bytes((len("Élite".encode()),))
                + "Élite".encode()
                + struct.pack(">q", (1 << 45) + 3),
            ),
        )
        self.assertEqual(
            {"rank_id": 99},
            guild_wire.decode_request(14088, struct.pack(">q", 99)),
        )
        self.assertEqual(
            {"rank_id": 99, "authorizations": (1 << 42), "name": "Élite"},
            guild_wire.decode_request(
                14815,
                struct.pack(">qq", 99, 1 << 42)
                + bytes((len("Élite".encode()),))
                + "Élite".encode(),
            ),
        )
        self.assertEqual(
            {"rank_id": 99, "position": -1},
            guild_wire.decode_request(15429, struct.pack(">qh", 99, -1)),
        )

    def test_creation_and_rank_requests_reject_bad_lengths_and_trailing_data(self):
        malformed = (
            (13757, struct.pack(">q", 1) + struct.pack(">i", 4) + b"x"),
            (15194, b"\x02\xc3" + struct.pack(">q", 1)),
            (14088, struct.pack(">q", 1) + b"x"),
            (14815, struct.pack(">qq", 1, 2) + b"\xff"),
            (15429, struct.pack(">qh", 1, 0) + b"x"),
        )
        for opcode, body in malformed:
            with self.subTest(opcode=opcode):
                with self.assertRaises(ValueError):
                    guild_wire.decode_request(opcode, body)

    def test_invitation_answer_accepts_only_native_boolean_bytes(self):
        self.assertEqual({"accepted": False}, guild_wire.decode_request(14995, b"\x00"))
        self.assertEqual({"accepted": True}, guild_wire.decode_request(14995, b"\x01"))
        for body in (b"", b"\x02", b"\x01\x00"):
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    guild_wire.decode_request(14995, body)

    def test_snapshot_local_section_contains_nested_ranks_and_full_width_values(self):
        model = _guild_model()
        section = guild_wire.local_section(model, 0.75)
        payload_length = struct.unpack(">H", section[:2])[0]
        payload = section[2:-4]

        self.assertEqual(payload_length, len(payload))
        self.assertEqual(0.75, struct.unpack(">f", section[-4:])[0])
        self.assertEqual(guild_wire.serialize_guild(model), payload)
        self.assertIn(guild_wire.serialize_rank(model["ranks"][0]), payload)
        self.assertIn(guild_wire.serialize_member(model["members"][0]), payload)
        self.assertIn("Gremio ñ".encode(), payload)
        self.assertIn(b"\x18" + _varint((1 << 40) + 7), payload)

    def test_snapshot_and_codec_enforce_required_fields_and_wire_limits(self):
        with self.assertRaisesRegex(ValueError, "Missing required"):
            guild_wire.serialize_guild({"guildId": 1})
        model = _guild_model()
        model["ranks"] = "not-a-sequence"
        with self.assertRaisesRegex(ValueError, "list or tuple"):
            guild_wire.serialize_guild(model)
        with self.assertRaisesRegex(ValueError, "int64"):
            guild_wire.remote_info(1 << 63, 0, 1, "Guild")
        with self.assertRaisesRegex(ValueError, "signed int64"):
            guild_wire.serialize_rank(
                {"id": 1, "name": "Rank", "authorizations": 1 << 63, "position": 0}
            )
        member = dict(_guild_model()["members"][0])
        member["sex"] = b""
        with self.assertRaisesRegex(ValueError, "exactly one byte"):
            guild_wire.serialize_member(member)
        with self.assertRaisesRegex(ValueError, "native byte length"):
            guild_wire.creation_ack("ñ" * 64)
        with self.assertRaisesRegex(ValueError, "moderation factor"):
            guild_wire.local_section(_guild_model(), float("inf"))

    def test_remote_identity_ack_and_delta_envelopes_roundtrip_layouts(self):
        remote = guild_wire.remote_info(456, 123456, 3, "Gremio ñ")
        name = "Gremio ñ".encode()
        self.assertEqual(struct.pack(">qqhH", 456, 123456, 3, len(name)) + name, remote)

        opcode, ack = guild_wire.creation_ack("Gremio ñ")
        self.assertEqual(1000, opcode)
        self.assertEqual(bytes((len(name),)) + name, ack)

        opcode, deltas = guild_wire.delta_envelope(456, [(2, b"abc")])
        self.assertEqual(15367, opcode)
        self.assertEqual(struct.pack(">qiib", 456, 1, 3, 2) + b"abc", deltas)

    @staticmethod
    def _format22(section):
        return b"\x16" + bytes(range(1, 32)) + section + b"NATION!!"

    def test_variable_guild_section_replacement_preserves_actor_prefix_and_suffix(self):
        original = self._format22(guild_wire.local_section(None, 0.25))
        model = _guild_model()
        updated = guild_wire.replace_local_entity(original, model, 0.5)
        expected_section = guild_wire.local_section(model, 0.5)

        self.assertEqual(original[:32], updated[:32])
        self.assertEqual(expected_section, updated[32:-8])
        self.assertEqual(original[-8:], updated[-8:])
        self.assertEqual(46 + len(guild_wire.serialize_guild(model)), len(updated))
        self.assertEqual(46, len(original))

    def test_local_actor_update_carries_variable_entity_length_and_i64_identity(self):
        entity = self._format22(guild_wire.local_section(_guild_model(), 0.5))
        opcode, body = guild_wire.local_actor_update(0x0001000000000007, entity)
        character_id, length = struct.unpack(">qH", body[:10])

        self.assertEqual(15548, opcode)
        self.assertEqual(0x0001000000000007, character_id)
        self.assertEqual(len(entity), length)
        self.assertEqual(entity, body[10:])

    def test_actor_codecs_reject_bad_or_inconsistent_format22_entities(self):
        for entity in (b"", b"\x15" + b"\0" * 45, b"\x16" + b"\0" * 44):
            with self.subTest(entity_length=len(entity)):
                with self.assertRaises(ValueError):
                    guild_wire.replace_local_entity(entity, _guild_model())
                with self.assertRaises(ValueError):
                    guild_wire.local_actor_update(1, entity)

        valid = self._format22(guild_wire.local_section(None))
        with self.assertRaises(ValueError):
            guild_wire.local_actor_update(1 << 63, valid)

    def test_company_wire_carries_guild_identity_without_changing_neutral_xp(self):
        _, hero_body = hero_wire.company(
            123,
            456,
            guild_id=789,
            company_snapshot=CompanySnapshot(123, 456, 0, 789, 1, True),
        )
        self.assertEqual(
            (1, 1, 123, 456, 0, 789, 0, 1, 1),
            struct.unpack(">IIqqiqIiB", hero_body),
        )
        _, hero_without_guild = hero_wire.company(
            123, 456, company_snapshot=CompanySnapshot(123, 456, 0, 0, 1, True)
        )
        self.assertEqual(0, struct.unpack(">IIqqiqIiB", hero_without_guild)[5])

        character = {
            "id": 456,
            "guild_native": {"guildId": 789},
            "equipment_criterion_context": {
                "company_snapshot": CompanySnapshot(
                    123, 456, 0, 789, 603, True
                ).record()
            },
        }
        company_body = social.company(123, character)
        fields = struct.unpack(">qqiqIiB", company_body)
        self.assertEqual((123, 456, 0, 789), fields[:4])
        self.assertEqual(603, fields[5])
        self.assertEqual(1, fields[6])
        neutral = struct.unpack(
            ">qqiqIiB",
            social.company(
                123,
                {
                    "id": 456,
                    "equipment_criterion_context": {
                        "company_snapshot": CompanySnapshot(
                            123, 456, 0, 0, 603, True
                        ).record()
                    },
                },
            ),
        )
        self.assertEqual(0, neutral[3])
        self.assertEqual(603, neutral[5])


if __name__ == "__main__":
    unittest.main()
