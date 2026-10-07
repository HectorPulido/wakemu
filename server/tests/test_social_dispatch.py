import struct
import unittest

from wakfu_server.social_dispatch import (
    decode_request,
    encode_add_friend_ack,
    encode_add_ignore_ack,
    encode_bootstrap,
    encode_dnd_status,
    encode_remove_friend_ack,
    encode_remove_ignore_ack,
)
from wakfu_server.social_wire import (
    decode_add_friend_ack as decode_friend_ack,
    decode_add_ignore_ack as decode_ignore_ack,
    decode_do_not_disturb_status,
    decode_friend_lists,
    decode_remove_friend_ack as decode_friend_remove,
    decode_remove_ignore_ack as decode_ignore_remove,
)


class SocialDispatchCodecTests(unittest.TestCase):
    def test_native_add_requests_decode_character_names_and_reject_trailing_data(self):
        self.assertEqual({"character_name": "Luna"}, decode_request(784, b"\x04Luna"))
        self.assertEqual(
            {"character_name": "Éva"},
            decode_request(657, "Éva".encode()[:0] + b"\x04\xc3\x89va"),
        )
        for body in (b"", b"\x00", b"\x05Luna", b"\x04Luna!", b"\x02\xff\xfe"):
            with self.subTest(body=body), self.assertRaises(ValueError):
                decode_request(784, body)

    def test_remove_and_dnd_requests_are_exact_fixed_layouts(self):
        account_id = 0x0102030405060708
        self.assertEqual(
            {"account_id": account_id},
            decode_request(672, struct.pack(">q", account_id)),
        )
        self.assertEqual(
            {"account_id": account_id},
            decode_request(799, struct.pack(">q", account_id)),
        )
        self.assertEqual({}, decode_request(12449, b""))
        for body in (b"", struct.pack(">q", -1), struct.pack(">q", 0), bytes(9)):
            with self.subTest(body=body), self.assertRaises(ValueError):
                decode_request(672, body)
        with self.assertRaises(ValueError):
            decode_request(12449, b"\x00")
        with self.assertRaises(ValueError):
            decode_request(777, b"")

    def test_add_ack_encoders_match_native_decoders_and_character_profile(self):
        contact = {
            "account_id": 9,
            "account_name": "A",
            "character_name": "C",
            "breed_id": 71,
            "sex": 1,
            "xp": 300,
        }
        self.assertEqual(
            decode_friend_ack(encode_add_friend_ack(contact)),
            {
                "account_id": 9,
                "account_name": "A",
                "character_name": "C",
                "breed_id": 71,
                "sex": 1,
                "xp": 300,
            },
        )
        self.assertEqual(
            decode_ignore_ack(encode_add_ignore_ack(contact)),
            {"account_id": 9, "account_name": "A", "character_name": "C"},
        )
        for invalid in (
            {**contact, "account_id": True},
            {**contact, "character_name": ""},
            {**contact, "breed_id": True},
            {**contact, "sex": 2},
            {**contact, "xp": -1},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                encode_add_friend_ack(invalid)

    def test_remove_ack_encoders_match_decoders_and_dnd_requires_boolean(self):
        self.assertEqual(
            decode_friend_remove(encode_remove_friend_ack(41)), {"account_id": 41}
        )
        removed_ignore = {"account_id": 42, "account_name": "Owner"}
        self.assertEqual(
            decode_ignore_remove(encode_remove_ignore_ack(removed_ignore)),
            removed_ignore,
        )
        for status in (False, True):
            body = encode_dnd_status(status)
            self.assertEqual(decode_do_not_disturb_status(body), status)
        for status in (0, 1, None):
            with self.subTest(status=status), self.assertRaises(ValueError):
                encode_dnd_status(status)

    def test_bootstrap_is_replaceable_authoritative_630_protobuf(self):
        snapshot = {
            "friends": [{"account_id": 1, "account_name": "A", "is_online": False}],
            "ignored": [{"account_id": 2, "account_name": "B", "is_online": True}],
            "do_not_disturb": True,
        }
        payload = encode_bootstrap(snapshot)
        self.assertEqual(
            {
                "friends": snapshot["friends"],
                "ignored": snapshot["ignored"],
            },
            decode_friend_lists(payload),
        )
        self.assertEqual(b"", encode_bootstrap({"friends": [], "ignored": []}))
        with self.assertRaises(ValueError):
            encode_bootstrap({"friends": [], "ignored": "bad"})


if __name__ == "__main__":
    unittest.main()
