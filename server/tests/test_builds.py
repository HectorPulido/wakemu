from pathlib import Path
import struct
import tempfile
import unittest
from wakfu_server.store import Store
from wakfu_server import builds, wire
from protocol_codec import Reader


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "world.sqlite3"
        self.store = Store(self.path)
        self.account = self.store.register("builder", "local-builder-password")["id"]
        self.character = self.store.create_character(self.account, "Builder", breed=8)
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        sheet = b"".join(
            wire.proto_field(tag, value)
            for tag, value in [(8, 0), (18, b"My build"), (24, 1), (56, 0)]
        )
        self.blobs = {"sheet": sheet, "equipment": b"", "deck": b"", "aptitudes": b""}

    def tearDown(self):
        self.temp.cleanup()

    def test_save_response_and_reopen_are_authoritative(self):
        body = struct.pack(">q", self.character["id"]) + b"".join(
            struct.pack(">I", len(self.blobs[key])) + self.blobs[key]
            for key in builds.KEYS
        )
        char, index, blobs = builds.decode(body)
        saved = self.store.save_build(self.account, self.generation, char, index, blobs)
        reopened = Store(self.path).character(self.account, char)
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

    def test_owned_equipment_selection_and_removal_persist_atomically(self):
        from wakfu_server.inventory_items import grant

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=6 WHERE id=?", (self.character["id"],)
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
            Store(self.path).character(self.account, self.character["id"])[
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
        self.assertEqual([entry[8] for entry in entries], [0, 1])
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
