import struct
import unittest
from postgres_case import PostgresCase
from wakfu_server import builds, wire
from protocol_codec import Reader


class BuildTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("builder", "local-builder-password")["id"]
        self.character = self.store.create_character(self.account, "Builder", breed=8)
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        sheet = b"".join(
            wire.proto_field(tag, value)
            for tag, value in [(8, 0), (18, b"My build"), (24, 1), (56, 0)]
        )
        self.blobs = {"sheet": sheet, "equipment": b"", "deck": b"", "aptitudes": b""}

    def test_save_response_and_reopen_are_authoritative(self):
        body = struct.pack(">q", self.character["id"]) + b"".join(
            struct.pack(">I", len(self.blobs[key])) + self.blobs[key]
            for key in builds.KEYS
        )
        char, index, blobs = builds.decode(body)
        saved = self.store.save_build(self.account, self.generation, char, index, blobs)
        reopened = self.reopen().character(self.account, char)
        self.assertEqual(saved["builds"], reopened["builds"])
        r = Reader(builds.response(reopened, index))
        self.assertEqual(
            (r.number("q"), r.number("i"), r.number("b"), r.number("B")),
            (char, 0, 0, 1),
        )
        values = [r.take(r.number("I")) for _ in range(4)]
        r.finish()
        self.assertEqual(values[0], self.blobs["sheet"])
        self.assertEqual(values[1], builds.EMPTY_EQUIPMENT)
        self.assertEqual(values[3], builds.EMPTY_APTITUDES)
        from wakfu_server.spells import default_deck

        self.assertEqual(values[2], default_deck(reopened))

    def test_failed_edit_returns_prior_authority_without_claiming_success(self):
        packets = builds.rejection_messages(self.character, 0, wp=6, status=9)
        self.assertEqual([opcode for opcode, _ in packets], [13078, 12284, 13046])
        r = Reader(packets[1][1])
        self.assertEqual(
            (r.number("q"), r.number("i"), r.number("b"), r.number("B")),
            (self.character["id"], 0, 9, 1),
        )
        values = [r.take(r.number("I")) for _ in range(4)]
        r.finish()
        self.assertEqual(values[1], builds.EMPTY_EQUIPMENT)
        self.assertEqual(values[3], builds.EMPTY_APTITUDES)
        self.assertEqual(self.character["builds"], {})
        # A rejected newly-created sheet must not be invented as saved.
        self.assertEqual(
            [
                op
                for op, _ in builds.rejection_messages(
                    self.character, 2, wp=6, status=2
                )
            ],
            [12284],
        )

    def test_combat_blocked_save_restores_prior_deck_without_resource_packets(self):
        saved = self.store.save_build(
            self.account, self.generation, self.character["id"], 0, self.blobs
        )
        changed = {**self.blobs, "deck": b"optimistic invalid edit"}
        body = struct.pack(">q", saved["id"]) + b"".join(
            struct.pack(">I", len(changed[key])) + changed[key] for key in builds.KEYS
        )
        packets = builds.blocked_save_messages(saved, body)
        self.assertEqual([op for op, _ in packets], [12284])
        r = Reader(packets[0][1])
        self.assertEqual(
            (r.number("q"), r.number("i"), r.number("b"), r.number("B")),
            (saved["id"], 0, 2, 1),
        )
        values = [r.take(r.number("I")) for _ in range(4)]
        r.finish()
        from wakfu_server.spells import default_deck

        self.assertEqual(values[2], default_deck(saved))
        self.assertEqual(
            self.store.character(self.account, saved["id"])["builds"], saved["builds"]
        )
        with self.assertRaises(ValueError):
            builds.blocked_save_messages(
                saved, struct.pack(">q", saved["id"] + 1) + body[8:]
            )

    def test_session_replacement_and_other_account_cannot_mutate_build(self):
        other = self.store.register("second", "local-other-password")["id"]
        foreign = self.store.begin_session(other)
        with self.assertRaises(ValueError):
            self.store.save_build(other, foreign, self.character["id"], 0, self.blobs)
        self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            self.store.save_build(
                self.account, self.generation, self.character["id"], 0, self.blobs
            )
        self.assertFalse(
            self.store.character(self.account, self.character["id"])["builds"]
        )

    def test_unowned_equipment_and_aptitude_points_are_rejected(self):
        for key, payload in [
            ("equipment", wire.proto_field(10, b"item id")),
            ("aptitudes", wire.proto_field(34, b"bonus")),
        ]:
            with self.assertRaises(ValueError):
                self.store.save_build(
                    self.account,
                    self.generation,
                    self.character["id"],
                    0,
                    {**self.blobs, key: payload},
                )
        self.assertFalse(
            self.store.character(self.account, self.character["id"])["builds"]
        )

    def test_saved_build_replaces_reconnect_build_slot(self):
        saved = self.store.save_build(
            self.account, self.generation, self.character["id"], 0, self.blobs
        )
        original = wire.proto_field(8, 0) + wire.proto_field(
            18, self.blobs["sheet"].replace(b"My build", b"Old name")
        )
        entries = [
            value
            for tag, value in wire.proto_fields(builds.build_set(saved, original))
            if tag == 18
        ]
        self.assertEqual(entries[0], self.blobs["sheet"])

    def test_reconnect_deck_collection_includes_empty_owned_slots_and_selected_index(
        self,
    ):
        from wakfu_server.spells import default_deck, encode_deck

        for index, deck in ((1, encode_deck([], [], 1)), (2, b"")):
            sheet = b"".join(
                wire.proto_field(tag, value)
                for tag, value in [
                    (8, index),
                    (18, f"Build {index}".encode()),
                    (24, 1),
                    (56, 0),
                ]
            )
            self.store.save_build(
                self.account,
                self.generation,
                self.character["id"],
                index,
                {"sheet": sheet, "equipment": b"", "deck": deck, "aptitudes": b""},
            )
        selected = self.store.activate_build(
            self.account, self.generation, self.character["id"], 1, in_fight=False
        )
        reopened = self.reopen().character(self.account, self.character["id"])
        self.assertEqual(reopened["active_build_index"], 1)
        self.assertEqual(reopened["builds"][1]["deck"], encode_deck([], [], 1).hex())

        body = builds.deck_collection(reopened)
        length = struct.unpack_from(">H", body)[0]
        self.assertEqual(length, len(body) - 2)
        collection = memoryview(body)[2:]
        count = struct.unpack_from(">i", collection)[0]
        offset = 4
        decks = {}
        for _ in range(count):
            index = struct.unpack_from(">b", collection, offset)[0]
            offset += 1
            start = offset
            active_count = struct.unpack_from(">i", collection, offset)[0]
            offset += 4 + active_count * 4
            passive_count = struct.unpack_from(">i", collection, offset)[0]
            offset += 4 + passive_count * 4 + 4
            decks[index] = bytes(collection[start:offset])
        self.assertEqual(offset, len(collection))
        self.assertEqual(set(decks), {0, 1, 2})
        self.assertEqual(decks[1], encode_deck([], [], 1))
        self.assertEqual(decks[2], default_deck(reopened))
        opcode, selected_body = builds.selection_message(reopened)
        self.assertEqual(opcode, 13811)
        self.assertEqual(struct.unpack(">qb", selected_body), (self.character["id"], 1))

    def test_owned_equipment_selection_and_removal_persist_atomically(self):
        from wakfu_server.inventory_items import grant

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=6 WHERE id=%s", (self.character["id"],)
            )
        destination = self.character["inventory_containers"][0]["uid"]
        item = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=2021,
            quantity=1,
            container=destination,
            slot=0,
            allowed_references={2021},
        )
        sheet = b"".join(
            wire.proto_field(tag, value)
            for tag, value in [(8, 0), (18, b"Owned gear"), (24, 6), (56, 0)]
        )
        equipment = wire.proto_field(
            10, wire.proto_field(8, item["uid"]) + wire.proto_field(16, 4)
        )
        blobs = {**self.blobs, "sheet": sheet, "equipment": equipment}
        saved = self.store.save_build(
            self.account, self.generation, self.character["id"], 0, blobs
        )
        self.assertEqual(saved["builds"][0]["equipment"], equipment.hex())
        self.assertEqual(
            self.reopen().character(self.account, self.character["id"])[
                "inventory_items"
            ],
            [item],
        )
        bad = wire.proto_field(
            10, wire.proto_field(8, item["uid"]) + wire.proto_field(16, 7)
        )
        with self.assertRaises(ValueError):
            self.store.save_build(
                self.account,
                self.generation,
                self.character["id"],
                0,
                {**blobs, "equipment": bad},
            )
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["builds"][0][
                "equipment"
            ],
            equipment.hex(),
        )
        empty = builds.EMPTY_EQUIPMENT
        removed = self.store.save_build(
            self.account,
            self.generation,
            self.character["id"],
            0,
            {**blobs, "equipment": empty},
        )
        self.assertEqual(removed["builds"][0]["equipment"], empty.hex())
        self.assertEqual(removed["inventory_items"], [item])

    def test_active_and_inactive_aptitude_builds_reconfigure_canonical_wounds(self):
        from wakfu_server.health_store import initialize, sync
        from wakfu_server.aptitudes import validate
        from wakfu_server.progression import level_xp

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=142 WHERE id=%s", (self.character["id"],)
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(142), self.character["id"]),
            )
        character = initialize(
            self.store, self.account, self.generation, self.character["id"], now_ms=1000
        )
        self.assertEqual((character["hp"], character["max_hp"]), (1470, 1470))
        character = sync(
            self.store,
            self.account,
            self.generation,
            character["id"],
            1470,
            1370,
            coefficient=1,
            now_ms=1000,
        )
        self.assertEqual(
            (character["hp"], character["max_hp"], character["hp_damage"]),
            (1370, 1470, 100),
        )

        hp_points = wire.proto_field(24, (1 << 64) - 1) + wire.proto_field(
            34, wire.proto_field(8, 31) + wire.proto_field(16, 21)
        )
        no_hp_points = wire.proto_field(24, (1 << 64) - 1)
        self.assertEqual(validate({"level": 142}, hp_points)["allocations"], {31: 21})
        active_sheet = b"".join(
            wire.proto_field(tag, value)
            for tag, value in [
                (8, 0),
                (18, b"Health config"),
                (24, 100),
                (56, 0),
                (64, 1),
            ]
        )
        active_blobs = {
            "sheet": active_sheet,
            "equipment": b"",
            "deck": b"",
            "aptitudes": hp_points,
        }
        saved_active = self.store.save_build(
            self.account, self.generation, self.character["id"], 0, active_blobs
        )
        self.assertEqual((saved_active["hp"], saved_active["max_hp"]), (1370, 1470))

        # The 12772 success path uses this response after committing the build;
        # its final actor refresh must expose the saved active aptitude sheet.
        refresh_packets = builds.response_messages(saved_active, 0, wp=6)
        self.assertEqual(
            [opcode for opcode, _ in refresh_packets],
            [12284, 12393, 12103, 13046],
        )
        refresh_body = refresh_packets[-1][1]
        self.assertEqual(
            struct.unpack_from(">q", refresh_body)[0], self.character["id"]
        )
        actor_blob = refresh_body[10:]
        stat_offset = 39
        stat_count = struct.unpack_from(">H", actor_blob, stat_offset)[0]
        hp_stats = {
            entry[0]: entry[1:]
            for entry in (
                struct.unpack_from(">Biiii", actor_blob, stat_offset + 2 + 17 * i)
                for i in range(stat_count)
            )
        }
        self.assertEqual((hp_stats[1][0], hp_stats[1][2]), (1370, 1470))

        inactive_sheet = b"".join(
            wire.proto_field(tag, value)
            for tag, value in [(8, 1), (18, b"Inactive config"), (24, 100), (56, 0)]
        )
        inactive_blobs = {
            "sheet": inactive_sheet,
            "equipment": b"",
            "deck": b"",
            "aptitudes": no_hp_points,
        }
        with self.store.connection() as db:
            baseline_started = db.execute(
                "SELECT started_at FROM character_regeneration WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()["started_at"]
        inactive = self.store.save_build(
            self.account, self.generation, self.character["id"], 1, inactive_blobs
        )
        self.assertEqual((inactive["hp"], inactive["max_hp"]), (1370, 1470))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT started_at FROM character_regeneration WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["started_at"],
                baseline_started,
            )

        selected = self.store.activate_build(
            self.account, self.generation, self.character["id"], 1, in_fight=False
        )
        self.assertEqual(
            (
                selected["active_build_index"],
                selected["hp"],
                selected["max_hp"],
                selected["hp_damage"],
            ),
            (1, 950, 1050, 100),
        )
        restored = self.store.activate_build(
            self.account, self.generation, self.character["id"], 0, in_fight=False
        )
        self.assertEqual(
            (restored["hp"], restored["max_hp"], restored["hp_damage"]),
            (1370, 1470, 100),
        )

        self.store.activate_build(
            self.account, self.generation, self.character["id"], 1, in_fight=False
        )
        deleted = self.store.delete_build(
            self.account, self.generation, self.character["id"], 1, in_fight=False
        )
        self.assertEqual(
            (
                deleted["active_build_index"],
                deleted["hp"],
                deleted["max_hp"],
                deleted["hp_damage"],
            ),
            (0, 1370, 1470, 100),
        )
        reopened = self.reopen().character(self.account, self.character["id"])
        self.assertEqual(
            (reopened["hp"], reopened["max_hp"], reopened["hp_damage"]),
            (1370, 1470, 100),
        )

    def test_health_reconfiguration_rolls_back_and_rejects_stale_lease(self):
        from unittest.mock import patch
        from wakfu_server.health_store import initialize, sync

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=142 WHERE id=%s", (self.character["id"],)
            )
        initialize(self.store, self.account, self.generation, self.character["id"])
        sync(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            1470,
            1370,
            coefficient=0,
        )
        inactive_sheet = b"".join(
            wire.proto_field(tag, value)
            for tag, value in [(8, 1), (18, b"Fallback"), (24, 100), (56, 0)]
        )
        self.store.save_build(
            self.account,
            self.generation,
            self.character["id"],
            1,
            {"sheet": inactive_sheet, "equipment": b"", "deck": b"", "aptitudes": b""},
        )
        before = self.store.character(self.account, self.character["id"])
        with patch(
            "wakfu_server.health_policy.reconfigure", side_effect=ValueError("injected")
        ):
            with self.assertRaisesRegex(ValueError, "injected"):
                self.store.activate_build(
                    self.account,
                    self.generation,
                    self.character["id"],
                    1,
                    in_fight=False,
                )
        rolled_back = self.store.character(self.account, self.character["id"])
        self.assertEqual(
            (
                rolled_back["active_build_index"],
                rolled_back["build_selection_revision"],
                rolled_back["hp"],
                rolled_back["max_hp"],
                rolled_back["hp_damage"],
            ),
            (
                before["active_build_index"],
                before["build_selection_revision"],
                before["hp"],
                before["max_hp"],
                before["hp_damage"],
            ),
        )

        self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            self.store.activate_build(
                self.account, self.generation, self.character["id"], 1, in_fight=False
            )
        stale = self.store.character(self.account, self.character["id"])
        self.assertEqual(
            (
                stale["active_build_index"],
                stale["build_selection_revision"],
                stale["hp"],
                stale["max_hp"],
                stale["hp_damage"],
            ),
            (
                before["active_build_index"],
                before["build_selection_revision"],
                before["hp"],
                before["max_hp"],
                before["hp_damage"],
            ),
        )

    def test_native_default_build_is_permanent_but_editable(self):
        sheet = b"".join(
            wire.proto_field(t, v)
            for t, v in [
                (8, 0),
                (18, b"Build por defecto"),
                (24, (1 << 64) - 1),
                (56, 1),
                (64, 1),
            ]
        )
        # Required native permanent flag is a boolean; it is not an editing ban.
        blobs = {**self.blobs, "sheet": sheet}
        saved = self.store.save_build(
            self.account, self.generation, self.character["id"], 0, blobs
        )
        self.assertEqual(bytes.fromhex(saved["builds"][0]["sheet"]), sheet)
        self.assertEqual(builds.response(saved, 0)[12:14], b"\x00\x01")

    def test_default_builds_do_not_inherit_level_twenty_presets(self):
        original = wire.proto_field(
            18,
            b"".join(
                wire.proto_field(t, v)
                for t, v in [(8, 2), (18, b""), (24, 20), (56, 0), (64, 1)]
            ),
        )
        entries = [
            dict(wire.proto_fields(v))
            for t, v in wire.proto_fields(builds.build_set(self.character, original))
            if t == 18
        ]
        self.assertEqual([entry[8] for entry in entries], [0])
        self.assertTrue(all(builds.signed32(entry[24]) == -1 for entry in entries))


class BootstrapRegistryTests(unittest.TestCase):
    def test_owned_gear_bootstrap_keeps_saved_units_and_indices(self):
        gear = (
            wire.proto_field(10, wire.proto_field(8, 987654) + wire.proto_field(16, 0))
            + builds.EMPTY_EQUIPMENT
        )
        character = {
            "id": 7,
            "level": 6,
            "builds": {
                0: {"equipment": gear.hex(), "aptitudes": ""},
                2: {"equipment": "", "aptitudes": ""},
            },
        }
        original = wire.proto_field(10, wire.proto_field(16, wire.TEMPLATE_CHARACTER))
        result = wire.attribute_sheets(
            struct.pack(">I", len(original)) + original, [character]
        )
        r = Reader(result)
        collection = list(wire.proto_fields(r.take(r.number("I"))))
        r.finish()
        registry = list(wire.proto_fields(collection[0][1]))
        self.assertEqual(dict(registry)[16], 7)
        entries = {
            dict(wire.proto_fields(value))[8]: dict(wire.proto_fields(value))[18]
            for tag, value in registry
            if tag == 10
        }
        self.assertEqual(entries, {0: gear, 2: builds.EMPTY_EQUIPMENT})
        # Aptitudes use ef field TWO, unlike hV gear field ONE.
        apt = builds.aptitude_registry(character)
        self.assertTrue(all(tag == 18 for tag, value in wire.proto_fields(apt)))
        packet = wire.adapt(12103, b"old fixture", 9, character)
        self.assertEqual(packet, struct.pack(">qI", 7, len(apt)) + apt)
        self.assertNotIn(gear, packet)
