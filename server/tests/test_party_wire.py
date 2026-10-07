import struct
import unittest

from wakfu_server.maps.party_wire import (
    invitation,
    invitation_answer,
    invitation_request,
    member_request,
    removed,
    roster,
)


def roster_member(**changes):
    member = {
        "association_id": 12,
        "id": 12345,
        "name": "AuditMember",
        "in_fight": True,
        "dead": False,
        "effective_level": 95,
        "hp": 87,
        "max_hp": 123,
        "level": 100,
        "breed": 8,
        "native_identity_flag": False,
        "portrait_variant": 1,
    }
    member.update(changes)
    return member


class PartyWireTests(unittest.TestCase):
    def test_native_invitation_answer_ow1031_fixture_and_default_inviter(self):
        # Captured layout: type, answer, length+UTF-8 inviter name, empty second
        # name for ordinary characters, inviter character ID (not party ID).
        body = bytes.fromhex("01 01 04 5a 6fc3ab 00 ffffffffffffffff")
        self.assertEqual(
            invitation_answer(body),
            {
                "accepted": True,
                "first_name": "Zoë",
                "second_name": "",
                "inviter_id": -1,
            },
        )

        empty_names = bytes.fromhex("01 00 00 00 ffffffffffffffff")
        self.assertEqual(
            invitation_answer(empty_names),
            {"accepted": False, "first_name": "", "second_name": "", "inviter_id": -1},
        )

    def test_native_answer_context_is_inviter_character_id(self):
        body = bytes.fromhex("01 01 01 41 00 0102030405060708")
        self.assertEqual(
            invitation_answer(body),
            {
                "accepted": True,
                "first_name": "A",
                "second_name": "",
                "inviter_id": 0x0102030405060708,
            },
        )

    def test_invitation_answer_rejects_bad_headers_names_and_context(self):
        valid = bytes.fromhex("01 01 01 41 01 42 ffffffffffffffff")
        malformed = (
            valid[:-1],  # truncated i64 context
            valid + b"\x00",  # trailing data
            bytes.fromhex("02 01 01 41 01 42 ffffffffffffffff"),
            bytes.fromhex("01 02 01 41 01 42 ffffffffffffffff"),
            bytes.fromhex("01 01 80") + bytes(128) + valid[5:],  # signed-byte length
            bytes.fromhex("01 01 01 ff 01 42 ffffffffffffffff"),  # malformed UTF-8
            bytes.fromhex("01 01 01 00 01 42 ffffffffffffffff"),  # embedded NUL
            bytes.fromhex("01 01 01 41 01 42 0000000000000000"),  # group zero
            bytes.fromhex("01 01 01 41 01 42 8000000000000000"),  # negative group
        )
        for body in malformed:
            with self.subTest(body=body.hex()), self.assertRaises(ValueError):
                invitation_answer(body)
        with self.assertRaises(ValueError):
            invitation_answer(bytearray(valid))

    def test_or1156_name_target_fixture_preserves_opaque_contexts(self):
        # Type 1, two opaque signed-i64 contexts, selector 0, byte-length UTF-8.
        body = bytes.fromhex("01 fffffffffffffff9 0102030405060708 00 04 5a c3b6 65")
        self.assertEqual(
            invitation_request(body),
            {
                "first_context": -7,
                "second_context": 0x0102030405060708,
                "target_name": "Zöe",
            },
        )

    def test_or1156_identity_target_fixture_preserves_opaque_contexts(self):
        # Selector 1 is followed directly by target i64; contexts are not IDs.
        body = bytes.fromhex("01 0000000000000000 fffffffffffffffe 01 0102030405060708")
        self.assertEqual(
            invitation_request(body),
            {
                "first_context": 0,
                "second_context": -2,
                "target_id": 0x0102030405060708,
            },
        )

    def test_or1156_name_limit_counts_utf8_bytes_and_rejects_empty(self):
        at_limit = "é" * 63 + "a"
        body = (
            b"\x01"
            + struct.pack(">qqB", -1, -2, 0)
            + bytes((127,))
            + at_limit.encode("utf-8")
        )
        self.assertEqual(invitation_request(body)["target_name"], at_limit)
        too_long = b"\x01" + struct.pack(">qqB", -1, -2, 0) + b"\x80" + bytes(128)
        with self.assertRaises(ValueError):
            invitation_request(too_long)
        empty = b"\x01" + struct.pack(">qqB", -1, -2, 0) + b"\x00"
        with self.assertRaisesRegex(ValueError, "target name"):
            invitation_request(empty)

    def test_or1156_rejects_truncation_trailing_type_selector_and_bad_target(self):
        name_prefix = b"\x01" + struct.pack(">qqB", -1, -2, 0)
        id_prefix = b"\x01" + struct.pack(">qqB", -1, -2, 1)
        malformed = (
            b"\x01" + bytes(16),  # missing selector / truncated body
            name_prefix + b"\x03ab",  # declared name exceeds body
            name_prefix + b"\x01A\x00",  # trailing byte
            name_prefix + b"\x01\xff",  # invalid UTF-8
            b"\x02" + name_prefix[1:] + b"\x00\x01A",  # wrong party type
            b"\x01" + struct.pack(">qqB", -1, -2, 2) + b"\x01A",  # selector 2
            id_prefix + struct.pack(">q", 0),
            id_prefix + struct.pack(">q", -1),
            id_prefix + struct.pack(">q", -(1 << 63)),
            id_prefix + struct.pack(">q", 1) + b"\x00",  # trailing byte
            id_prefix + struct.pack(">q", 1)[:-1],  # truncated i64
        )
        for body in malformed:
            with self.subTest(body=body.hex()), self.assertRaises(ValueError):
                invitation_request(body)
        with self.assertRaises(ValueError):
            invitation_request(bytearray(name_prefix + b"\x01A"))

    def test_og1072_encoder_matches_explicit_native_utf8_fixture(self):
        # Type byte 1, UTF-8 byte length 4, "Zoë", signed i64 identity.
        self.assertEqual(
            invitation(0x0102030405060708, "Zoë"),
            (1072, bytes.fromhex("01 04 5a 6fc3ab 0102030405060708")),
        )

    def test_invitation_name_limit_counts_utf8_bytes(self):
        within = "é" * 63 + "a"  # 127 encoded bytes
        opcode, body = invitation(7, within)
        self.assertEqual(opcode, 1072)
        self.assertEqual(body[1], 127)
        self.assertEqual(len(body), 2 + 127 + 8)
        with self.assertRaisesRegex(ValueError, "too long"):
            invitation(7, "é" * 64)  # 128 bytes, despite only 64 characters

    def test_invitation_encoder_rejects_bad_identity_and_name_types(self):
        for identity in (True, 0, -1, 1 << 63, 1.0):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                invitation(identity, "A")
        for name in ("", "A\x00B", b"A", None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                invitation(1, name)

    def test_ou1074_ov1066_member_request_explicit_native_fixture(self):
        # Both opcodes carry group i64 then member i64, without a wrapper/count.
        body = bytes.fromhex("0102030405060708 1112131415161718")
        expected = {"group_id": 0x0102030405060708, "member_id": 0x1112131415161718}
        for opcode in (1074, 1066):
            with self.subTest(opcode=opcode):
                self.assertEqual(member_request(body), expected)
        for body in (body[:-1], body + b"\x00", b"", bytearray(body)):
            with self.subTest(body=bytes(body).hex()), self.assertRaises(ValueError):
                member_request(body)

    def test_member_request_rejects_nonpositive_and_overflow_wire_ids(self):
        bad_values = (0, -1, -(1 << 63))
        for group_id in bad_values:
            body = struct.pack(">qq", group_id, 2)
            with self.subTest(group_id=group_id), self.assertRaises(ValueError):
                member_request(body)
        for member_id in bad_values:
            body = struct.pack(">qq", 1, member_id)
            with self.subTest(member_id=member_id), self.assertRaises(ValueError):
                member_request(body)
        # Values above signed i64 cannot appear in a native request body; the
        # encoders reject them before packing rather than wrapping them.
        with self.assertRaises(ValueError):
            invitation(1 << 63, "A")

    def test_oh1049_removed_fixture_has_group_then_ids_without_count(self):
        opcode, body = removed(0x0102030405060708, [9, 10])
        self.assertEqual(opcode, 1049)
        self.assertEqual(
            body,
            bytes.fromhex("0102030405060708 0000000000000009 000000000000000a"),
        )
        # No count prefix: the first eight bytes are exactly the group ID.
        self.assertEqual(struct.unpack_from(">q", body)[0], 0x0102030405060708)
        self.assertEqual(len(body), 8 + 2 * 8)

    def test_removed_rejects_missing_duplicate_or_invalid_identities(self):
        for group_id, members in (
            (True, [2]),
            (0, [2]),
            (-1, [2]),
            (1 << 63, [2]),
            (1, []),
            (1, [2, 2]),
            (1, [0]),
            (1, [-2]),
            (1, [1 << 63]),
            (1, {2}),
        ):
            with self.subTest(group_id=group_id, members=members), self.assertRaises(
                ValueError
            ):
                removed(group_id, members)

    def test_oe1184_matches_offline_java_human_member_record_fixture(self):
        # Native PartyRosterRecordProbe confirms the identity-section offsets;
        # fgn confirms sections 1/2/3/5/7 and the identity tail (breed, flag,
        # portrait variant) against the installed codecs.
        expected = bytes.fromhex(
            "010000000000002a00000800000000000030390001"
            "0000000000003039005b"
            "06000000001f010000004002000000420300000044"
            "05000000470700000058"
            "00000000000000000c00000000000030390b"
            "41756469744d656d62657200080001"
            "0101020003005f05000000570000007b0000000000000000070064"
        )
        self.assertEqual(
            roster(
                0x010000000000002A,
                12345,
                [roster_member()],
            ),
            (1184, expected),
        )
        # Record section count + fgj directory; offsets are relative to the
        # record and preserve native tag order (0,1,2,3,5,7).
        self.assertEqual(
            expected[31:62],
            bytes.fromhex(
                "06000000001f01000000400200000042030000004405000000470700000058"
            ),
        )
        self.assertEqual(
            expected[62:95],
            bytes.fromhex(
                "00000000000000000c00000000000030390b41756469744d656d62657200080001"
            ),
        )
        with self.assertRaisesRegex(ValueError, "leader is absent"):
            roster(
                0x010000000000002A,
                10434830,  # leader from the offline parser fixture is not listed there
                [roster_member()],
            )

    def test_oe1184_names_use_utf8_byte_lengths(self):
        party_id = 0x0100000000000001
        name = "é" * 63 + "a"  # 127 bytes, not 64
        _, body = roster(party_id, 12345, [roster_member(id=12345, name=name)])
        record_start = 31
        identity_start = record_start + 1 + 6 * 5
        self.assertEqual(body[identity_start + 1 + 16], 127)
        self.assertEqual(
            body[identity_start + 1 + 17 : identity_start + 1 + 17 + 127],
            name.encode(),
        )
        with self.assertRaises(ValueError):
            roster(
                party_id,
                12345,
                [roster_member(id=12345, name="é" * 64)],
            )

    def test_oe1184_requires_party_high_byte_leader_and_unique_member_ids(self):
        member = roster_member(id=7, association_id=8, name="A")
        for party_id in (7, 0x0200000000000001, True, 1 << 63):
            with self.subTest(party_id=party_id), self.assertRaises(ValueError):
                roster(party_id, 7, [member])
        for leader_id, members in (
            (9, [member]),
            (7, [member, dict(member, name="Duplicate")]),
        ):
            with self.subTest(leader_id=leader_id, members=members), self.assertRaises(
                ValueError
            ):
                roster(0x0100000000000001, leader_id, members)
        for members in (
            [],
            [member] * 7,
            [roster_member(id=True)],
            [roster_member(association_id=0)],
            [roster_member(name="")],
            [roster_member(name="A\x00B")],
        ):
            with self.subTest(members=members), self.assertRaises(ValueError):
                roster(0x0100000000000001, 7, members)

    def test_oe1184_rejects_malformed_status_level_and_health_fields(self):
        invalid = (
            {"in_fight": 1},
            {"dead": 0},
            {"level": True},
            {"level": 0},
            {"level": 1 << 15},
            {"effective_level": False},
            {"effective_level": 0},
            {"effective_level": 1 << 15},
            {"hp": True},
            {"hp": -1},
            {"hp": 124},
            {"max_hp": 0},
            {"max_hp": 1 << 31},
            {"breed": True},
            {"breed": 0},
            {"breed": 1 << 15},
            {"portrait_variant": True},
            {"portrait_variant": -1},
            {"portrait_variant": 128},
            {"native_identity_flag": 0},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                roster(0x0100000000000001, 12345, [roster_member(**changes)])


if __name__ == "__main__":
    unittest.main()
