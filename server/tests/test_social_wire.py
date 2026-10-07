import unittest

from wakfu_server.social_wire import (
    add_friend_request,
    add_ignore_request,
    decode_add_friend_ack,
    decode_add_ignore_ack,
    decode_do_not_disturb_status,
    decode_friend_lists,
    decode_remove_friend_ack,
    decode_remove_ignore_ack,
    do_not_disturb_request,
    encode_friend_lists,
    remove_friend_request,
    remove_ignore_request,
)


class SocialWireTests(unittest.TestCase):
    def test_native_dnd_action_has_fixed_flags_and_empty_body(self):
        self.assertEqual(do_not_disturb_request(), bytes.fromhex("000000070330a1"))

    def test_add_friend_and_ignore_use_native_utf8_byte_length(self):
        self.assertEqual(
            add_friend_request("Luna"), bytes.fromhex("0000000c040310044c756e61")
        )
        self.assertEqual(add_ignore_request("é"), bytes.fromhex("0000000a04029102c3a9"))

    def test_remove_friend_and_ignore_use_raw_big_endian_i64(self):
        contact_id = 0x0102030405060708
        self.assertEqual(
            remove_friend_request(contact_id),
            bytes.fromhex("0000000f0402a00102030405060708"),
        )
        self.assertEqual(
            remove_ignore_request(contact_id),
            bytes.fromhex("0000000f04031f0102030405060708"),
        )
        # Native commands use -1 when they cannot resolve a contact locally.
        self.assertEqual(
            remove_friend_request(-1)[7:], bytes.fromhex("ffffffffffffffff")
        )

    def test_contact_name_rejects_empty_and_native_u8_overflow(self):
        for encode in (add_friend_request, add_ignore_request):
            with self.subTest(encode=encode.__name__), self.assertRaises(ValueError):
                encode("")
            with self.subTest(encode=encode.__name__), self.assertRaises(ValueError):
                encode("é" * 128)

    def test_contact_ids_are_strictly_signed_i64_and_bool_is_not_an_id(self):
        for encode in (remove_friend_request, remove_ignore_request):
            for value in (True, -(1 << 63) - 1, 1 << 63, "42"):
                with self.subTest(encode=encode.__name__, value=value):
                    with self.assertRaises(ValueError):
                        encode(value)

    def test_friend_list_bootstrap_matches_fa_repeated_fields_and_et_schema(self):
        friend = {
            "account_id": 1,
            "account_name": "A",
            "is_online": True,
            "character_name": "X",
            "notify": False,
            "breed_id": 71,
            "sex": 1,
            "commentary": "hi",
            "xp": 300,
        }
        ignored = {"account_id": 2, "account_name": "B", "is_online": False}
        golden = bytes.fromhex(
            "0a1d0801120141200192030158980300a00347a80301b203026869b803ac02"
            "120708021201422000"
        )
        self.assertEqual(encode_friend_lists([friend], [ignored]), golden)
        self.assertEqual(
            decode_friend_lists(golden), {"friends": [friend], "ignored": [ignored]}
        )
        self.assertEqual(decode_friend_lists(b""), {"friends": [], "ignored": []})

    def test_friend_list_codec_rejects_invalid_types_and_truncation(self):
        for contact in (
            {"account_id": True},
            {"account_id": 1 << 63},
            {"is_online": 1},
            {"account_name": 4},
            {"unknown_field": "x"},
            {"account_id": 1},
        ):
            with self.subTest(contact=contact), self.assertRaises(ValueError):
                encode_friend_lists([contact])
        for payload in (b"\x0a\x02\x08", b"\x0a\x01\x08", b"\x0a\x01\x0c"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                decode_friend_lists(payload)
        with self.assertRaises(ValueError):
            decode_friend_lists(
                bytes.fromhex("0a020801")
            )  # missing required name/status

    def test_add_contact_acks_identify_account_and_character_separately(self):
        friend_ack = bytes.fromhex("01410143 0000000000000009 0047 01 000000000000012c")
        self.assertEqual(
            decode_add_friend_ack(friend_ack),
            {
                "account_id": 9,
                "account_name": "A",
                "character_name": "C",
                "breed_id": 71,
                "sex": 1,
                "xp": 300,
            },
        )
        ignore_ack = bytes.fromhex("0000000000000009 01 41 01 43")
        self.assertEqual(
            decode_add_ignore_ack(ignore_ack),
            {"account_id": 9, "account_name": "A", "character_name": "C"},
        )

    def test_remove_contact_acks_and_dnd_status_have_native_body_layout(self):
        self.assertEqual(
            decode_remove_friend_ack(bytes.fromhex("0102030405060708")),
            {"account_id": 0x0102030405060708},
        )
        self.assertEqual(
            decode_remove_ignore_ack(bytes.fromhex("0102030405060708 01 41")),
            {"account_id": 0x0102030405060708, "account_name": "A"},
        )
        self.assertTrue(decode_do_not_disturb_status(b"\x01"))
        self.assertFalse(decode_do_not_disturb_status(b"\x00"))
        for decoder, payload in (
            (decode_remove_friend_ack, b""),
            (decode_remove_friend_ack, bytes(9)),
            (decode_remove_ignore_ack, bytes(8)),
            (decode_add_friend_ack, b"\x02x"),
            (decode_add_ignore_ack, bytes(9)),
            (
                decode_add_friend_ack,
                bytes.fromhex("0141 0143 0000000000000009 0047 01"),
            ),
            (decode_add_ignore_ack, bytes.fromhex("0000000000000009 01 ff 01 43")),
            (decode_do_not_disturb_status, b"\x01\x00"),
        ):
            with self.subTest(decoder=decoder.__name__, payload=payload):
                with self.assertRaises(ValueError):
                    decoder(payload)


if __name__ == "__main__":
    unittest.main()
