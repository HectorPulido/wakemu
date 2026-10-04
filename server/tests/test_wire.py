import struct
import unittest
from protocol_codec import Reader, decode_appearance
from wakfu_server import wire


class WireTests(unittest.TestCase):
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
