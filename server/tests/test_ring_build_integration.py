"""Owned ring save, ACK, registry, and PostgreSQL reconnect integration."""
import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server import builds, wire
from wakfu_server.equipment_stats import bonuses, effective_character
from wakfu_server.health import maximum
from wakfu_server.inventory_items import grant
from wakfu_server.progression import level_xp
from protocol_codec import Reader


class RingBuildIntegrationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("ring-test", "private-local-test-password")[
            "id"
        ]
        self.char = self.store.create_character(self.account, "Ring Test", breed=11)
        self.generation = self.store.begin_session(self.account, ttl=10000)
        self.store.select_character(self.account, self.generation, self.char["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=20,hp=80,max_hp=%s,hp_damage=%s,health_dead=false WHERE id=%s",
                (maximum(11, 20), maximum(11, 20) - 80, self.char["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(20), self.char["id"]),
            )
        self.char = self.store.character(self.account, self.char["id"])
        self.items = [
            grant(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                reference=2022,
                quantity=1,
                container=self.char["inventory_containers"][0]["uid"],
                slot=slot,
                allowed_references={2022},
            )
            for slot in (0, 1)
        ]

    def blobs(self, slot=7):
        return dict(
            sheet=b"".join(
                wire.proto_field(t, v)
                for t, v in [(8, 0), (18, b"Own ring"), (24, (1 << 64) - 1), (56, 1)]
            ),
            equipment=wire.proto_field(
                10,
                wire.proto_field(8, self.items[0]["uid"]) + wire.proto_field(16, slot),
            ),
            deck=b"",
            aptitudes=b"",
        )

    def save(self, blobs):
        request = struct.pack(">q", self.char["id"]) + b"".join(
            struct.pack(">I", len(blobs[k])) + blobs[k] for k in builds.KEYS
        )
        character, index, decoded = builds.decode(request)
        return self.store.save_build(
            self.account, self.generation, character, index, decoded
        )

    def test_ring_ack_registry_reopening_keep_real_uid_once(self):
        blobs = self.blobs()
        saved = self.save(blobs)
        self.assertEqual(bonuses(saved)["stats"], {1: 5, 20: 5})
        expected_hp = maximum(11, 20) + 5 - (maximum(11, 20) - 80)
        self.assertEqual(
            (saved["hp"], saved["max_hp"], saved["hp_damage"]),
            (expected_hp, maximum(11, 20) + 5, maximum(11, 20) - 80),
        )
        r = Reader(builds.response_messages(saved, 0, wp=6)[0][1])
        self.assertEqual(
            (r.number("q"), r.number("i"), r.number("b"), r.number("B")),
            (saved["id"], 0, 0, 1),
        )
        decoded = {key: r.take(r.number("I")) for key in builds.KEYS}
        r.finish()
        self.assertEqual(decoded["equipment"], blobs["equipment"])
        original = wire.proto_field(10, wire.proto_field(16, wire.TEMPLATE_CHARACTER))
        packet = wire.attribute_sheets(
            struct.pack(">I", len(original)) + original, [saved]
        )
        registry = list(wire.proto_fields(dict(wire.proto_fields(packet[4:]))[10]))
        self.assertEqual(dict(registry)[16], saved["id"])
        entries = {
            dict(wire.proto_fields(value))[8]: dict(wire.proto_fields(value))
            for tag, value in registry
            if tag == 10
        }
        self.assertEqual(set(entries), {0})
        self.assertEqual(entries[0][8], 0)
        self.assertEqual(entries[0][18], blobs["equipment"])
        loaded = self.reopen().character(self.account, saved["id"])
        self.assertEqual(loaded["builds"], saved["builds"])
        self.assertEqual(effective_character(loaded)["max_hp"], maximum(11, 20) + 5)
        repeated = self.save(blobs)
        self.assertEqual(
            (repeated["hp"], repeated["max_hp"], repeated["hp_damage"]),
            (expected_hp, maximum(11, 20) + 5, maximum(11, 20) - 80),
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS count FROM character_builds").fetchone()[
                    "count"
                ],
                1,
            )
            self.assertEqual(
                bytes(
                    db.execute("SELECT equipment FROM character_builds").fetchone()[
                        "equipment"
                    ]
                ),
                blobs["equipment"],
            )

    def test_move_between_ring_slots_and_reject_second_same_equipped_without_partial_save(
        self,
    ):
        self.save(self.blobs(7))
        moved = self.save(self.blobs(8))
        self.assertEqual(
            moved["builds"][0]["equipment"], self.blobs(8)["equipment"].hex()
        )
        bad = dict(
            self.blobs(8),
            equipment=self.blobs(8)["equipment"]
            + wire.proto_field(
                10, wire.proto_field(8, self.items[1]["uid"]) + wire.proto_field(16, 7)
            ),
        )
        with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
            self.save(bad)
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["builds"],
            moved["builds"],
        )
