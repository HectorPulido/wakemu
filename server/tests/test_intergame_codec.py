import struct
import unittest

from wakfu_server import intergame_codec as codec


class IntergameCodecTests(unittest.TestCase):
    def test_negative_native_identifier_round_trip(self):
        body = codec.response(
            7,
            name="user.FriendList",
            value={
                "values": [{"user": {"user_id": 6, "name": "Peer", "tag": "6"}}],
            },
        )
        response = codec.decode("transport.Frame", body)["response"]
        self.assertEqual(response["correlation_id"], 7)
        self.assertEqual(response["payload"]["id"], -1150791598)
        self.assertEqual(
            codec.decode("user.FriendList", response["payload"]["data"])["values"][0][
                "user"
            ]["name"],
            "Peer",
        )

    def test_native_spin_total_length_and_control_frames(self):
        self.assertEqual(codec.spin(2), b"\x00\x00\x00\x05\x02")
        self.assertEqual(codec.spin(0, b"abc"), struct.pack(">IB", 8, 0) + b"abc")
        for kind, body in [
            (4, b""),
            (True, b""),
            (1, b"x"),
            (0, b"x" * codec.MAX_FRAME),
        ]:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                codec.spin(kind, body)

    def test_malformed_wire_and_invalid_oneof_are_rejected(self):
        for body in [
            b"\x00",
            b"\x0a\x05x",
            b"\x08\x80",
            b"\x0b",
            b"\x08" + b"\xff" * 11,
        ]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                codec.decode("transport.Frame", body)
        with self.assertRaises(ValueError):
            codec.encode("transport.Frame", {"request": {}, "event": {}})

    def test_utf8_events_and_unknown_future_fields(self):
        event = codec.event(
            "channel.ChannelMessageCreatedEvt",
            {
                "message": {
                    "channel_id": "DM_5_6",
                    "content": "Español 🌱",
                    "author": {"user_id": 6},
                }
            },
        )
        value = codec.decode(
            "transport.Frame", event + codec.varint(100 << 3) + b"\x01"
        )
        payload = value["event"]
        self.assertEqual(
            codec.decode("channel.ChannelMessageCreatedEvt", payload["data"])[
                "message"
            ]["content"],
            "Español 🌱",
        )

    def test_descriptor_ids_are_bijective_and_installed_provenance_matches(self):
        self.assertEqual(len(codec.IDS), 41)
        self.assertEqual(len(codec.NAMES), 41)
        self.assertEqual(codec.IDS["channel.CreateChannelMessageCmd"], 1835442294)
