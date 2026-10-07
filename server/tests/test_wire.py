import struct
import unittest
from protocol_codec import Reader, decode_appearance
from wakfu_server import wire


class WireTests(unittest.TestCase):
    @staticmethod
    def _world_r_e_direction(body):
        offset = body.index(wire.INITIAL_POSITION)
        # Native rE fixed prefix: XYZ, map, direction, and position-present.
        return struct.unpack_from(">iihqBB", body, offset)

    def test_own_spawn_refresh_and_bootstrap_preserve_all_world_directions(self):
        from wakfu_server.native_transports import bootstrap

        name = b"Pekebu"
        template = (
            struct.pack(
                ">BqBqH",
                11,
                wire.TEMPLATE_CHARACTER,
                1,
                wire.TEMPLATE_ACCOUNT,
                len(name),
            )
            + name
            + struct.pack(">iihqBB", -12, -8, -1, 1134, 3, 1)
            + bytes(20)  # Native secondary rH position and remaining sections.
        )
        base = dict(
            id=42,
            account_id=501,
            name="Pekebu",
            level=None,
            x=-12,
            y=-8,
            z=-1,
            map_id=1134,
            direction=3,
        )

        for direction in range(8):
            with self.subTest(direction=direction):
                character = dict(base, direction=direction)
                spawned = wire.spawn_player(template, character)
                spawn_entity_len = struct.unpack_from(">H", spawned, 2 + 1 + 8)[0]
                spawn_entity = spawned[2 + 1 + 8 + 2 : 2 + 1 + 8 + 2 + spawn_entity_len]
                self.assertEqual(direction, self._world_r_e_direction(spawn_entity)[4])

                opcode, refresh = wire.refresh_player(template, character)
                self.assertEqual(15548, opcode)
                char_id, entity_len = struct.unpack_from(">qh", refresh)
                self.assertEqual(42, char_id)
                refresh_entity = refresh[10 : 10 + entity_len]
                self.assertEqual(
                    direction, self._world_r_e_direction(refresh_entity)[4]
                )

                packets = bootstrap(character)
                self.assertEqual(13974, packets[1][0])
                encoded = packets[1][1]
                first_len = struct.unpack_from(">H", encoded)[0]
                entity = encoded[2 : 2 + first_len]
                self.assertEqual(direction, self._world_r_e_direction(entity)[4])

    def test_world_direction_adapters_reject_bool_and_out_of_range_values(self):
        from wakfu_server.native_transports import bootstrap

        character = dict(
            id=42,
            account_id=501,
            name="Pekebu",
            level=None,
            x=-12,
            y=-8,
            z=-1,
            map_id=1134,
            direction=3,
        )
        template = (
            struct.pack(
                ">BqBqH", 11, wire.TEMPLATE_CHARACTER, 1, wire.TEMPLATE_ACCOUNT, 6
            )
            + b"Pekebu"
            + struct.pack(">iihqBB", -12, -8, -1, 1134, 3, 1)
            + bytes(20)
        )
        for direction in (True, -1, 8):
            with self.subTest(direction=direction), self.assertRaises(ValueError):
                wire.spawn_player(template, dict(character, direction=direction))
            with self.subTest(bootstrap_direction=direction), self.assertRaises(
                ValueError
            ):
                bootstrap(dict(character, direction=direction))

    def test_private_chat_echo_uses_recipient_character_and_sender_account_ids(self):
        body = wire.private_chat(
            9001,
            {"id": 41, "name": "Remitente"},
            {"id": 73, "name": "Destinatario"},
            "hola ñ",
        )
        recipient = "Destinatario".encode("utf-8")
        sender = "Remitente".encode("utf-8")
        text = "hola ñ".encode("utf-8")
        expected = (
            struct.pack(">B", len(recipient))
            + recipient
            + struct.pack(">qB", 73, len(sender))
            + sender
            + struct.pack(">BBqB", 6, 4, 9001, 0)
            + struct.pack(">H", len(text))
            + text
        )
        self.assertEqual(body, expected)
        self.assertNotEqual(9001, 41)  # account ID differs from sender character ID
        self.assertNotEqual(9001, 73)  # and from recipient character ID

    def test_private_chat_utf8_byte_limits_allow_127_and_2048(self):
        sender_name = "ñ" * 63 + "a"  # 127 UTF-8 bytes, despite 64 code points
        recipient_name = "é" * 63 + "a"
        text = "ñ" * 1024  # exactly 2048 UTF-8 bytes
        body = wire.private_chat(
            9001,
            {"id": 41, "name": sender_name},
            {"id": 73, "name": recipient_name},
            text,
        )
        self.assertEqual(body[0], 127)
        self.assertEqual(body[1:128], recipient_name.encode("utf-8"))
        recipient_end = 1 + len(recipient_name.encode("utf-8"))
        self.assertEqual(
            struct.unpack(">qB", body[recipient_end : recipient_end + 9]), (73, 127)
        )
        sender_start = recipient_end + 9
        sender_end = sender_start + len(sender_name.encode("utf-8"))
        self.assertEqual(body[sender_start:sender_end], sender_name.encode("utf-8"))
        text_length_offset = sender_end + 11
        self.assertEqual(
            struct.unpack(">H", body[text_length_offset : text_length_offset + 2])[0],
            2048,
        )
        self.assertEqual(len(body[text_length_offset + 2 :]), 2048)

    def test_private_chat_sender_name_uses_unsigned_nq_byte_while_recipient_is_signed(
        self,
    ):
        # Oi's leading recipient-name byte is signed by the native parser;
        # the nested NQ sender-name byte is read as unsigned (0..255).
        recipient_name = "r" * 127
        recipient_end = 1 + len(recipient_name.encode("utf-8"))
        for source_length in (128, 255):
            with self.subTest(source_length=source_length):
                sender_name = "s" * source_length
                body = wire.private_chat(
                    9001,
                    {"id": 41, "name": sender_name},
                    {"id": 73, "name": recipient_name},
                    "x",
                )
                self.assertEqual(body[0], 127)
                self.assertEqual(body[recipient_end + 8], source_length)
                self.assertEqual(
                    body[recipient_end + 9 : recipient_end + 9 + source_length],
                    sender_name.encode(),
                )

    def test_private_chat_and_user_not_found_have_distinct_name_length_widths(self):
        name = "Éva"  # three characters, four UTF-8 bytes
        response = wire.private_chat(
            9001, {"id": 41, "name": "Yo"}, {"id": 73, "name": name}, "x"
        )
        error = wire.private_chat_error(101, name)
        name_bytes = name.encode("utf-8")
        self.assertEqual(
            response[: 1 + len(name_bytes)], bytes([len(name_bytes)]) + name_bytes
        )
        self.assertEqual(error, struct.pack(">hH", 101, len(name_bytes)) + name_bytes)
        self.assertEqual(error[:2], b"\x00\x65")  # 101 is a two-byte signed code
        self.assertEqual(error[2:4], b"\x00\x04")  # error name length is u16
        # NE/cis.a reads a u16-length string for each native 101/102/103 case.
        self.assertEqual(
            wire.private_chat_error(102, "Destino"), b"\x00\x66\x00\x07Destino"
        )
        self.assertEqual(
            wire.private_chat_error(103, "Destino"), b"\x00\x67\x00\x07Destino"
        )

    def test_private_chat_rejects_names_text_and_identity_outside_native_bounds(self):
        sender = {"id": 41, "name": "S"}
        recipient = {"id": 73, "name": "R"}
        for account_id, source, target, text in (
            (9001, {"id": 41, "name": "s" * 256}, recipient, "x"),
            (9001, sender, {"id": 73, "name": "é" * 64}, "x"),
            (9001, sender, recipient, "ñ" * 1025),
            (9001, sender, recipient, ""),
            (0, sender, recipient, "x"),
            (True, sender, recipient, "x"),
            (9001, sender, {"id": 0, "name": "R"}, "x"),
        ):
            with self.subTest(account_id=account_id, text_len=len(text)):
                with self.assertRaises(ValueError):
                    wire.private_chat(account_id, source, target, text)

    def test_private_chat_error_rejects_unsupported_codes_and_bad_recipient_names(self):
        for code in (100, 141, True, "101"):
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    wire.private_chat_error(code, "Destino")
        self.assertEqual(wire.private_chat_error(104), b"\x00\x68")
        self.assertEqual(wire.private_chat_error(140), b"\x00\x8c")
        for name in ("", "ñ" * 64):
            with self.subTest(name_bytes=len(name.encode("utf-8"))):
                for code in (101, 102, 103):
                    with self.subTest(code=code), self.assertRaises(ValueError):
                        wire.private_chat_error(code, name)
        for code in (101, 102, 103):
            with self.subTest(code=code), self.assertRaises(ValueError):
                wire.private_chat_error(code)

    def test_character_entry_never_inherits_template_active_states(self):
        import hashlib
        from unittest.mock import patch

        # Both entry and subsequent entity snapshots carry this section.
        for kind in (10, 11):
            captured = b"foreign class running effects"
            body = bytes([kind]) + b"prefix" + captured + b"suffix"
            layout = {
                "template_sha256": hashlib.sha256(body).hexdigest(),
                "sections": [
                    {"name": "RUNNING_EFFECTS", "start": 7, "end": 7 + len(captured)}
                ],
            }
            with patch.dict(wire.ENTITY_LAYOUTS, {kind: layout}):
                actual = wire.minimal_entity(body, {"level": 6, "breed": 11})
            self.assertEqual(actual, body[:7] + bytes(2) + b"suffix")

    def test_all_fixture_entity_formats_clear_inherited_nation(self):
        import hashlib
        from unittest.mock import patch

        for kind, name in (
            (10, "NATION_ID"),
            (11, "NATION_ID"),
            (5, "CHARACTER_LIST_NATION_ID"),
        ):
            body = bytes([kind]) + b"prefix" + struct.pack(">i", 30) + b"suffix"
            layout = {
                "template_sha256": hashlib.sha256(body).hexdigest(),
                "sections": [{"name": name, "start": 7, "end": 11}],
            }
            with patch.dict(wire.ENTITY_LAYOUTS, {kind: layout}):
                actual = wire.minimal_entity(body, {"level": 1})
            self.assertEqual(actual, body[:7] + bytes(4) + body[11:])

    def test_nation_synchro_clears_captured_rank_jobs_and_vote_state(self):
        import hashlib
        from unittest.mock import patch

        captured = struct.pack(">qqqBBB", 123, 456, 789, 2, 1, 5)
        body = b"\x0bprefix" + captured + b"suffix"
        layout = {
            "template_sha256": hashlib.sha256(body).hexdigest(),
            "sections": [{"name": "NATION_SYNCHRO", "start": 7, "end": 34}],
        }
        with patch.dict(wire.ENTITY_LAYOUTS, {11: layout}):
            actual = wire.minimal_entity(body, {"level": 1})
        self.assertEqual(actual, body[:7] + bytes(27) + body[34:])

    def test_passport_info_is_reset_with_character_nation(self):
        import hashlib
        from unittest.mock import patch

        # The one-byte rr section is separate from qZ/NATION_ID. Keep it
        # authoritative too, so a template cannot carry passport state over.
        body = b"\x0a-prefix" + b"\x7f" + b"-suffix"
        start = len(b"\x0a-prefix")
        layout = {
            "template_sha256": hashlib.sha256(body).hexdigest(),
            "sections": [{"name": "PASSEPORT_INFO", "start": start, "end": start + 1}],
        }
        with patch.dict(wire.ENTITY_LAYOUTS, {10: layout}):
            actual = wire.minimal_entity(body, {"level": 1})
        self.assertEqual(actual, body[:start] + b"\x00" + body[start + 1 :])

    def test_account_inventory_empty_proto_replaces_captured_items(self):
        proto = b"captured items"
        body = struct.pack(">III", 1, 4, len(proto)) + proto
        self.assertEqual(wire.adapt(13873, body, 7), struct.pack(">III", 1, 4, 0))
        for invalid in (body[:-1], body + b"\x00"):
            with self.assertRaises(ValueError):
                wire.adapt(13873, invalid, 7)

    def test_account_kamas_is_initialized_and_inherited_balance_replaced(self):
        original = struct.pack(">IIq", 1, 6, 999999)
        self.assertEqual(wire.adapt(13873, original, 7), struct.pack(">IIq", 1, 6, 0))
        self.assertEqual(wire.account_kamas(123), struct.pack(">IIq", 1, 6, 123))
        for amount in (-1, 1 << 63, True):
            with self.assertRaises(ValueError):
                wire.account_kamas(amount)

    def test_later_kama_update_cannot_restore_fixture_balance(self):
        self.assertEqual(
            wire.adapt(13021, struct.pack(">q", 13638), 7), struct.pack(">q", 0)
        )
        for invalid in (b"", bytes(7), bytes(9)):
            with self.assertRaises(ValueError):
                wire.adapt(13021, invalid, 7)

    def test_native_live_wallet_refresh_mutates_existing_account_balance(self):
        # Native cye/chS reads this absolute i64 and applies it to aTJ.cXc(),
        # preserving the existing foF observer chain.
        body = struct.pack(">q", 999999)
        self.assertEqual(wire.adapt(12753, body, 7, kamas=123), struct.pack(">q", 123))
        self.assertEqual(wire.account_kamas_update(123), struct.pack(">q", 123))
        for invalid in (b"", bytes(7), bytes(9)):
            with self.assertRaises(ValueError):
                wire.adapt(12753, invalid, 7, kamas=123)
        for amount in (-1, 1 << 63, True):
            with self.assertRaises(ValueError):
                wire.account_kamas_update(amount)

    def test_fresh_attribute_sheet_drops_inherited_allocations(self):
        old = wire.proto_field(10, b"captured allocations") + wire.proto_field(
            16, wire.TEMPLATE_CHARACTER
        )
        proto = wire.proto_field(10, old)
        result = wire.attribute_sheets(
            struct.pack(">I", len(proto)) + proto, [{"id": 7, "level": 1}]
        )
        reader = Reader(result)
        sheets = list(wire.proto_fields(reader.take(reader.number("I"))))
        reader.finish()
        fields = list(wire.proto_fields(sheets[0][1]))
        self.assertEqual(fields[1], (16, 7))
        entry = list(wire.proto_fields(fields[0][1]))
        self.assertEqual(entry[0], (8, 0))
        self.assertEqual(list(wire.proto_fields(entry[1][1])), [(424, (1 << 64) - 1)])
        self.assertNotIn(b"captured allocations", result)

    def test_appearance_wire_roundtrip_preserves_all_colors_and_signed_values(self):
        appearance = {
            "skinColor": -6720193,
            "hairColor": -10873225,
            "pupilColor": -16777216,
            "costumeColor1": -4209466,
            "costumeColor6": -12229251,
            "clothIndex": 0,
            "faceIndex": 3,
            "sex": 0,
            "currentTitle": -1,
        }
        section = wire.appearance_section(appearance)
        self.assertEqual(struct.unpack(">H", section[:2])[0], len(section) - 2)
        decoded = decode_appearance(section[2:])
        self.assertEqual({key: decoded[key] for key in appearance}, appearance)
        self.assertTrue(
            all(
                key in decoded
                for key in (
                    "costumeColor2",
                    "costumeColor3",
                    "costumeColor4",
                    "costumeColor5",
                )
            )
        )
        for invalid in ({"skinColor": 1 << 31}, {"sex": False}, {"unknown": 1}):
            with self.assertRaises(ValueError):
                wire.appearance_section(invalid)

    def test_equipment_appearance_removal_preserves_following_sections(self):
        for kind, start in ((5, 147), (10, 10336), (11, 808)):
            body = (
                bytes([kind])
                + bytes(start - 1)
                + b"\x0c"
                + bytes(108)
                + b"next section"
            )
            self.assertEqual(
                wire.without_equipment_appearance(body, {"level": 1}),
                body[:start] + b"\x00" + b"next section",
            )
            with self.assertRaises(ValueError):
                wire.without_equipment_appearance(
                    body[:start] + b"\x03" + body[start + 1 :], {"level": 1}
                )

    def test_initial_progression_checks_layout_and_resets_only_xp(self):
        for kind, offset in ((5, 262), (10, 4614)):
            body = (
                bytes([kind])
                + bytes(offset - 1)
                + struct.pack(">q", 4094076145)
                + b"tail"
            )
            result = wire.initial_progression(body, {"level": 1})
            self.assertEqual(result[:offset], body[:offset])
            self.assertEqual(result[offset : offset + 8], bytes(8))
            self.assertEqual(result[offset + 8 :], b"tail")
            with self.assertRaises(ValueError):
                wire.initial_progression(result, {"level": 1})

    def test_character_levels_removes_unowned_fixture_records(self):
        tail = b"next section"
        body = (
            struct.pack(">IIIqHqH", 2, 0, 2, 123, 50, wire.TEMPLATE_CHARACTER, 148)
            + tail
        )
        result = wire.character_levels(body, {"id": 7, "account_id": 9, "level": 1})
        self.assertEqual(result, struct.pack(">IIIqH", 2, 0, 1, 7, 1) + tail)
        other = struct.pack(">IIq", 1, 8, wire.TEMPLATE_ACCOUNT)
        self.assertEqual(
            wire.character_levels(other, {"id": 7, "account_id": 9, "level": 1}),
            struct.pack(">IIq", 1, 8, 9),
        )

    def test_captured_named_haven_bags_are_removed_and_other_objects_preserved(self):
        bag = struct.pack(">qqH", -42, 3700, 6) + b"Manama" + struct.pack(">q", 123)
        other = struct.pack(">qqH", -43, 9000, 3) + b"npc" + struct.pack(">q", 456)
        original = b"\x00\x02" + bag + other
        self.assertEqual(
            wire.without_captured_haven_bags(original), b"\x00\x01" + other
        )
        self.assertEqual(
            wire.remove_captured_haven_bags(original), struct.pack(">Hq", 1, -42)
        )
        with self.assertRaises(ValueError):
            wire.without_captured_haven_bags(original[:-1])
        with self.assertRaises(ValueError):
            wire.without_captured_haven_bags(b"\x00\x00extra")

    def test_remote_movement_preserves_exact_stair_path(self):
        from protocol_codec import decode_body

        request = struct.pack(">iiihB", 1, 7, 14, -1, 3) + bytes([1, 0x3F, 0x40])
        response = wire.movement_path(42, request)
        decoded = decode_body("in", 13852, response)
        self.assertEqual(decoded["actor_id"], 42)
        self.assertEqual(decoded["start_position"], {"x": 7, "y": 14, "z": -1})
        self.assertEqual([step["dz"] for step in decoded["steps"]], [1, -1, 0])
        self.assertEqual(response[8:], request[4:])
        with self.assertRaises(ValueError):
            wire.movement_path(42, request[:-1])

    def test_chat_encodes_local_identity_and_utf8(self):
        body = wire.chat({"id": 42, "name": "Álpha"}, "Hola, ¿qué tal?")
        r = Reader(body)
        self.assertEqual(r.text("B"), "Álpha")
        self.assertEqual(r.take(2), bytes([6, 4]))
        self.assertEqual(r.number("q"), 42)
        self.assertEqual(r.number("B"), 1)
        self.assertEqual(r.text("H"), "Hola, ¿qué tal?")
        r.finish()

    def test_captured_players_are_removed_but_npcs_remain(self):
        player = struct.pack(">BqH", 0, 20, 3) + b"one"
        npc = struct.pack(">BqH", 1, -42, 3) + b"two"
        self.assertEqual(
            wire.without_captured_players(b"\x00\x02" + player + npc), b"\x00\x01" + npc
        )

    def test_attribute_sheet_ids_and_lengths_are_reencoded(self):
        aptitude = b"\x0a\x04\x08\x00\x12\x00"
        original = wire.proto_field(
            10, aptitude + wire.proto_field(16, wire.TEMPLATE_CHARACTER)
        )
        body = struct.pack(">I", len(original)) + original
        result = wire.attribute_sheets(body, [{"id": 1}, {"id": 16384}])
        r = Reader(result)
        sets = list(wire.proto_fields(r.take(r.number("I"))))
        r.finish()
        self.assertEqual(len(sets), 2)
        for (_, value), expected in zip(sets, (1, 16384)):
            self.assertEqual(
                list(wire.proto_fields(value)),
                [(10, b"\x08\x00\x12\x00"), (16, expected)],
            )

    def test_variable_name_preserves_identity_flag_and_blob_lengths(self):
        prefix = b"\x05" + struct.pack(
            ">qBq", wire.TEMPLATE_CHARACTER, 0, wire.TEMPLATE_ACCOUNT
        )
        captured = prefix + b"\x00\x06Pekebu" + b"\x00\x0f\x00"
        template = b"\x01" + struct.pack(">I", len(captured)) + captured + b"\x00"
        output = wire.character_list(template, 7, [{"id": 21, "name": "Longer Name"}])
        r = Reader(output)
        self.assertEqual(r.number("B"), 1)
        blob = Reader(r.take(r.number("I")))
        self.assertEqual(blob.number("B"), 5)
        self.assertEqual(blob.number("q"), 21)
        self.assertEqual(blob.number("B"), 0)
        self.assertEqual(blob.number("q"), 7)
        self.assertEqual(blob.text("H"), "Longer Name")
        self.assertEqual(blob.take(3), b"\x00\x0f\x00")
        blob.finish()
        self.assertEqual(r.number("B"), 0)
        r.finish()

    def test_high_level_characters_keep_clean_inventory_and_sheets(self):
        from wakfu_server.progression import level_xp

        character = {"id": 7, "level": 200}
        self.assertEqual(level_xp(1), 0)
        self.assertEqual(level_xp(200), 59929868921)
        self.assertTrue(all(level_xp(n) < level_xp(n + 1) for n in range(1, 200)))
        for invalid in (0, 201, True, 1.0):
            with self.assertRaises(ValueError):
                level_xp(invalid)
        self.assertEqual(
            wire.adapt(13078, b"captured inventory", 9, character),
            struct.pack(">qIB", 7, 0, 0),
        )
        old = wire.proto_field(10, b"captured allocations") + wire.proto_field(
            16, wire.TEMPLATE_CHARACTER
        )
        proto = wire.proto_field(10, old)
        result = wire.attribute_sheets(
            struct.pack(">I", len(proto)) + proto, [character]
        )
        self.assertNotIn(b"captured allocations", result)
        for kind, offset in ((5, 262), (10, 4614)):
            body = (
                bytes([kind])
                + bytes(offset - 1)
                + struct.pack(">q", 4094076145)
                + b"tail"
            )
            result = wire.initial_progression(body, character)
            self.assertEqual(struct.unpack_from(">q", result, offset)[0], level_xp(200))
            self.assertEqual(result[offset + 8 :], b"tail")

    def test_empty_equipment_uses_current_character_level_sentinel(self):
        sheet = wire.proto_field(10, b"captured item") + wire.proto_field(424, 148)
        entry = wire.proto_field(8, 0) + wire.proto_field(18, sheet)
        proto = wire.proto_field(10, entry) + wire.proto_field(
            16, wire.TEMPLATE_CHARACTER
        )
        body = struct.pack(">qI", wire.TEMPLATE_CHARACTER, len(proto)) + proto
        result = wire.empty_equipment_sheets(body, {"id": 7, "level": 200})
        r = Reader(result)
        self.assertEqual(r.number("q"), 7)
        fields = list(wire.proto_fields(r.take(r.number("I"))))
        r.finish()
        nested = dict(wire.proto_fields(dict(wire.proto_fields(fields[0][1]))[18]))
        self.assertEqual(nested, {424: (1 << 64) - 1})
        self.assertNotIn(b"captured item", result)


if __name__ == "__main__":
    unittest.main()
