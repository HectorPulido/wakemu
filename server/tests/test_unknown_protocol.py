import struct
import unittest
from protocol_codec import decode_body


class AdditionalProtocolTests(unittest.TestCase):
    def test_current_collect_messages_are_protobuf_not_legacy_fixed_width(self):
        # Negative x is sign-extended int32 and is ten bytes in protobuf.
        body = b"\x08\x01\x10" + b"\xff" * 9 + b"\x01\x18\x02"
        self.assertEqual(
            decode_body("out", 12995, body), {"action_id": 1, "x": -1, "y": 2}
        )
        self.assertEqual(
            decode_body("out", 13481, b"\x08\x02\x10\x80\x01"),
            {"action_id": 2, "monster_id": 128},
        )
        for body in (b"\x10\x80", b"\x0a\x00", b"\x00", b"\x08" + b"\x80" * 10):
            with self.assertRaises(ValueError):
                decode_body("out", 12995, body)

    def test_interactive_element_request_preserves_java_padding(self):
        body = struct.pack(">qh", 123, -4) + b"\x00\x00"
        self.assertEqual(
            decode_body("out", 12870, body),
            {"interactive_element_id": 123, "action_id": -4, "padding_hex": "0000"},
        )
        for body in (body[:-1], body + b"\x00"):
            with self.assertRaises(ValueError):
                decode_body("out", 12870, body)

    def test_item_use_optional_position_is_exact(self):
        simple = struct.pack(">qB", 42, 0)
        self.assertEqual(
            decode_body("out", 12659, simple), {"item_id": 42, "has_position": False}
        )
        targeted = struct.pack(">qBiih", 42, 1, -1, 2, -3)
        self.assertEqual(
            decode_body("out", 12659, targeted)["position"], {"x": -1, "y": 2, "z": -3}
        )
        with self.assertRaises(ValueError):
            decode_body("out", 12659, simple + b"\x00")
        with self.assertRaises(ValueError):
            decode_body("out", 12659, targeted[:-1])

    def test_counted_ids_reject_negative_count_and_extra_bytes(self):
        body = struct.pack(">Biii", 1, 2, 9, -4)
        self.assertEqual(
            decode_body("out", 12962, body), {"flag": True, "ids": [9, -4]}
        )
        for body in (
            struct.pack(">Bi", 1, -1),
            struct.pack(">Bi", 1, 100),
            body + b"\x00",
        ):
            with self.assertRaises(ValueError):
                decode_body("out", 12962, body)

    def test_new_fixed_layouts_require_exact_lengths(self):
        layouts = {
            363: ("Biq", (3, 7, 1000)),
            12058: ("ii", (4, 5)),
            12296: ("qiBi", (1, 2, 1, 3)),
            12656: ("qqqb", (1, 2, 3, 4)),
            12921: ("i", (1,)),
            12925: ("iB", (2, 1)),
            13130: ("qiihB", (1, 2, 3, -1, 1)),
            13260: ("qqiih", (1, 2, 3, 4, -1)),
            13429: ("bh", (-1, 12)),
            13498: ("iq", (1, 2)),
            13510: ("i", (3,)),
            15494: ("bii", (1, 2, 3)),
        }
        for opcode, (fmt, values) in layouts.items():
            body = struct.pack(">" + fmt, *values)
            with self.subTest(opcode=opcode):
                self.assertIsNotNone(decode_body("out", opcode, body))
                for invalid in (body[:-1], body + b"\x00"):
                    with self.assertRaises(ValueError):
                        decode_body("out", opcode, invalid)
        self.assertEqual(decode_body("out", 23481, b""), {})
        with self.assertRaises(ValueError):
            decode_body("out", 23481, b"\x00")

    def test_inbound_actor_layouts_are_exact(self):
        layouts = {
            13462: ("qihBq", (1, 2, 3, 1, 4)),
            12782: ("iihhqi", (1, 2, -1, 3, 4, 5)),
            12634: ("qi", (1, 0)),
            13928: ("q", (1,)),
            13421: ("qiB", (1, 2, 1)),
            13948: ("qbffffffi", (1, 2, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7)),
            314: ("biqqq", (3, 2, 1, 2, 3)),
            23354: ("q", (100,)),
            12470: ("qhH", (10, 1, 0)),
            12916: ("iq", (2, 100)),
            13479: ("bih", (-1, 4, 1)),
            12401: ("qb", (10, 3)),
            12447: ("qbbb", (10, 0, 2, 1)),
            13249: ("qiih", (10, -3, 7, -1)),
            13259: ("qiihBB", (10, -3, 7, -1, 1, 0)),
            12436: ("qii", (10, 20, 30)),
            12318: ("ii", (4, 5)),
            12218: ("i", (4,)),
            12969: ("ibq", (4, -1, 10)),
            13417: ("qii", (10, 500, -1)),
            13021: ("q", (100,)),
        }
        for opcode, (fmt, values) in layouts.items():
            body = struct.pack(">" + fmt, *values)
            with self.subTest(opcode=opcode):
                self.assertIsNotNone(decode_body("in", opcode, body))
                for invalid in (body[:-1], body + b"\x00"):
                    with self.assertRaises(ValueError):
                        decode_body("in", opcode, invalid)

    def test_learned_spells_and_actor_attributes_bound_records(self):
        body = struct.pack(">qiqh", 10, 4778, 99, 1)
        result = decode_body("in", 12503, body)
        self.assertEqual(
            result["spells"], [{"reference_id": 4778, "uid": 99, "level": 1}]
        )
        self.assertEqual(decode_body("in", 12503, struct.pack(">q", 10))["spells"], [])
        for invalid in (body[:-1], body + b"\x00"):
            with self.assertRaises(ValueError):
                decode_body("in", 12503, invalid)
        attrs = struct.pack(">qbbii", 10, 1, 2, 50, 60)
        self.assertEqual(
            decode_body("in", 13060, attrs)["attributes"],
            [{"id": 2, "first_value": 50, "second_value": 60}],
        )
        for invalid in (attrs[:-1], attrs + b"\x00", struct.pack(">qb", 10, -1)):
            with self.assertRaises(ValueError):
                decode_body("in", 13060, invalid)

    def test_name_suggestions_use_signed_byte_lengths(self):
        self.assertEqual(
            decode_body("in", 23597, b"\x02\x03Uno\x03Dos"),
            {"suggested_names": ["Uno", "Dos"]},
        )
        for invalid in (b"\xff", b"\x01\xff", b"\x01\x03ab", b"\x00\x00"):
            with self.assertRaises(ValueError):
                decode_body("in", 23597, invalid)

    def test_inventory_object_and_objective_lengths_are_bounded(self):
        body = struct.pack(">qhi", 10, 3, 2) + b"ab" + b"\x01"
        self.assertEqual(
            decode_body("in", 12471, body),
            {
                "container_id": 10,
                "destination_position": 3,
                "item_binary_hex": "6162",
                "mAB": True,
            },
        )
        for invalid in (body[:-1], body + b"\x00", struct.pack(">qhi", 10, 3, -1)):
            with self.assertRaises(ValueError):
                decode_body("in", 12471, invalid)
        objective = struct.pack(">Biibq", 1, 2, 3, 1, 10)
        self.assertEqual(
            decode_body("in", 13411, objective),
            {"mEC": True, "atv": 2, "atu": 3, "actors": [10]},
        )
        for invalid in (
            objective[:-1],
            objective + b"\x00",
            struct.pack(">Biib", 1, 2, 3, -1),
        ):
            with self.assertRaises(ValueError):
                decode_body("in", 13411, invalid)

    def test_inherited_combat_headers_are_wire_fields_not_object_metadata(self):
        layouts = {
            13726: ("iiiq", (1, 2, 3, 4)),
            13337: ("iiiqq", (1, 2, 3, 4, 5)),
            13482: ("iiiqq", (1, 2, 3, 4, 5)),
            12502: ("iiiqii", (1, 2, 3, 4, 5, 6)),
            13494: ("iiiqb", (1, 2, 3, 4, 5)),
            12727: ("iiiqb", (1, 2, 3, 4, 2)),
            13970: ("iiiqiB", (1, 2, 3, 4, 5, 1)),
            13420: ("i", (1,)),
            13684: ("ii", (1, 2)),
            13887: ("iqiih", (1, 2, 3, 4, -1)),
            13205: ("qi", (1, 2)),
            13312: ("qi", (1, 2)),
            13832: ("qi", (1, 2)),
            13371: ("qiB", (1, 2, 1)),
            13422: ("qiq", (1, 2, 3)),
            13295: ("qiq", (1, 2, 3)),
        }
        for opcode, (fmt, values) in layouts.items():
            body = struct.pack(">" + fmt, *values)
            with self.subTest(opcode=opcode):
                self.assertIsNotNone(decode_body("in", opcode, body))
                for invalid in (body[:-1], body + b"\x00"):
                    with self.assertRaises(ValueError):
                        decode_body("in", opcode, invalid)
        self.assertEqual(decode_body("in", 13256, b""), {})
        with self.assertRaises(ValueError):
            decode_body("in", 13256, b"\x00")

    def test_verified_health_gauge_and_account_slots(self):
        self.assertEqual(
            decode_body("in", 13574, struct.pack(">qi", 8, -10000)),
            {"actor_id": 8, "gauge_value": -10000},
        )
        self.assertEqual(
            decode_body("in", 12436, struct.pack(">qii", 8, 60, 3)),
            {"actor_id": 8, "health": 60, "regeneration_coefficient": 3},
        )
        self.assertEqual(
            decode_body("in", 23992, b"\x02"), {"additional_character_slots": 2}
        )
        for opcode, body in ((13574, struct.pack(">qi", 8, 1)), (23992, b"\x01")):
            for invalid in (body[:-1], body + b"\x00"):
                with self.assertRaises(ValueError):
                    decode_body("in", opcode, invalid)

    def test_market_price_compression_and_monthly_completion(self):
        import zlib

        raw = struct.pack(">iBqq", 27, 5, 100, 300)
        body = zlib.compress(raw)
        self.assertEqual(
            decode_body("in", 14303, body),
            {
                "market_prices": [
                    {
                        "item_reference": 27,
                        "prices_by_variant_index": [100, -1, 300, -1, -1],
                    }
                ]
            },
        )
        for bad in (
            body[:-1],
            body + b"\0",
            zlib.compress(raw[:-1]),
            zlib.compress(struct.pack(">iB", 27, 32)),
        ):
            with self.assertRaises(ValueError):
                decode_body("in", 14303, bad)
        self.assertEqual(
            decode_body("in", 15529, struct.pack(">qhii", 7, 2, 23, 25)),
            {"actor_id": 7, "monthly_completed_dungeons": [23, 25]},
        )
        with self.assertRaises(ValueError):
            decode_body("in", 15529, struct.pack(">qh", 7, -1))

    def test_effect_execution_and_relocation_keep_padding(self):
        body = (
            struct.pack(">iiBBih", 1, 2, 0, 1, 3, 2)
            + b"ab"
            + struct.pack(">iiq", 4, 5, 6)
        )
        fields = decode_body("in", 12705, body)
        self.assertEqual(fields["effect_binary_hex"], "6162")
        self.assertEqual(fields["triplets"], [{"first": 4, "second": 5, "third": 6}])
        with self.assertRaises(ValueError):
            decode_body("in", 12705, body[:-1])
        relocation = struct.pack(">ihqiihB", 9, 1, 10, 11, 12, -1, 1) + bytes(4)
        self.assertEqual(
            decode_body("in", 13652, relocation),
            {
                "fight_id": 9,
                "actors": [{"actor_id": 10, "x": 11, "y": 12, "z": -1}],
                "force_immediate": True,
                "padding_hex": "00000000",
            },
        )
        with self.assertRaises(ValueError):
            decode_body("in", 13652, relocation[:-1])
