import unittest
import math
import struct

from psycopg.errors import CheckViolation
from postgres_case import PostgresCase
from wakfu_server.territory_weather import context, decode, save


class TerritoryWeatherTests(PostgresCase):
    # A real exported surface in map 1134, native territory 79201.
    character = {"map_id": 1134, "instance_id": 17}
    x, y, z = -23, -143, 70
    region_id = 79201

    @staticmethod
    def payload(weather_id, *, values=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)):
        return struct.pack(">qb6fi", 123456789, 7, *values, weather_id)

    def add_weather(self, map_id, instance_id, region_id, weather, payload):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO territory_weather(map_id,instance_id,region_id,weather,native_payload) "
                "VALUES(%s,%s,%s,%s,%s)",
                (map_id, instance_id, region_id, weather, payload),
            )

    def test_context_requires_exact_map_instance_and_native_region(self):
        # Each decoy matches two of the three lookup dimensions. None may act
        # as a fallback for the character's exact territory.
        self.add_weather(1134, 18, self.region_id, "STORM", self.payload(3))
        self.add_weather(1135, 17, self.region_id, "HEAVY", self.payload(2))
        self.add_weather(1134, 17, 79001, "LIGHT", self.payload(1))
        # Known catalog territories get an explicit LOCAL_POLICY ABSENT
        # baseline; decoy states from other scopes still do not leak in.
        local = context(self.store, self.character, x=self.x, y=self.y, z=self.z)
        self.assertEqual(local["weather"], "ABSENT")
        self.assertNotEqual(local["region_id"], 79001)

        payload = self.payload(3)
        save(
            self.store,
            map_id=1134,
            instance_id=17,
            region_id=self.region_id,
            payload=payload,
        )
        resolved = context(
            self.store,
            self.character,
            x=self.x,
            y=self.y,
            z=self.z,
        )
        self.assertEqual(resolved["weather"], "STORM")
        self.assertEqual(resolved["native_payload"], payload)
        self.assertEqual(resolved["revision"], 2)
        self.assertEqual(resolved["region_id"], self.region_id)

    def test_missing_weather_gets_local_baseline_but_unknown_territory_still_fails(
        self,
    ):
        # Exact native x/y ownership uses the explicit local baseline, and
        # changing height does not change the weather territory.
        first = context(self.store, self.character, x=self.x, y=self.y, z=self.z)
        second = context(self.store, self.character, x=self.x, y=self.y, z=self.z + 1)
        self.assertEqual(first["weather"], "ABSENT")
        self.assertEqual(first["region_id"], second["region_id"])
        with self.assertRaisesRegex(ValueError, "territory at position"):
            context(self.store, self.character, x=10000, y=10000, z=self.z)

    def test_database_rejects_unknown_weather_and_non_native_payload_lengths(self):
        invalid = (
            ("CLEAR", self.payload(0), 1),
            ("LIGHT", self.payload(1)[:-1], 1),
            ("LIGHT", self.payload(1) + b"x", 1),
            ("ABSENT", self.payload(0), 0),
        )
        for offset, (weather, payload, revision) in enumerate(invalid):
            with self.subTest(
                weather=weather, payload_len=len(payload), revision=revision
            ):
                with self.assertRaises(CheckViolation):
                    with self.store.connection() as db:
                        db.execute(
                            "INSERT INTO territory_weather("
                            "map_id,instance_id,region_id,weather,native_payload,revision) "
                            "VALUES(%s,%s,%s,%s,%s,%s)",
                            (
                                1134,
                                20,
                                self.region_id + offset,
                                weather,
                                payload,
                                revision,
                            ),
                        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM territory_weather WHERE map_id=1134 AND instance_id=20"
                ).fetchone()["count"],
                0,
            )

    def test_native_weather_codec_rejects_unknown_enum_and_nonfinite_values(self):
        valid = self.payload(2)
        self.assertEqual(decode(valid)["weather"], "HEAVY")
        self.assertEqual(decode(valid)["native_values"], (1, 2, 3, 4, 5, 6))
        malformed = (
            self.payload(4),
            self.payload(1, values=(math.nan, 2, 3, 4, 5, 6)),
            self.payload(1, values=(1, math.inf, 3, 4, 5, 6)),
            self.payload(1, values=(1, 2, 3, 4, 5, -math.inf)),
            bytearray(valid),
            valid[:-1],
        )
        for payload in malformed:
            with self.subTest(payload_type=type(payload).__name__, length=len(payload)):
                with self.assertRaises(ValueError):
                    decode(payload)

    def test_save_rejects_malformed_payload_and_unknown_native_region_before_writes(
        self,
    ):
        malformed = (
            self.payload(9),
            self.payload(0, values=(math.nan, 1, 2, 3, 4, 5)),
            self.payload(2, values=(1, 2, 3, 4, 5, math.inf)),
        )
        for payload in malformed:
            with self.subTest(payload=payload.hex()):
                with self.assertRaises(ValueError):
                    save(
                        self.store,
                        map_id=1134,
                        instance_id=17,
                        region_id=self.region_id,
                        payload=payload,
                    )
        with self.assertRaisesRegex(ValueError, "Unknown native map region"):
            save(
                self.store,
                map_id=1134,
                instance_id=17,
                region_id=123456,
                payload=self.payload(1),
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM territory_weather WHERE map_id=1134 AND instance_id=17"
                ).fetchone()["count"],
                0,
            )

    def test_save_upserts_revision_and_weather_is_scoped_per_instance(self):
        first = save(
            self.store,
            map_id=1134,
            instance_id=17,
            region_id=self.region_id,
            payload=self.payload(1),
        )
        self.assertEqual(first["weather"], "LIGHT")
        self.assertEqual(first["revision"], 1)
        second_payload = self.payload(3, values=(10, 20, 30, 40, 50, 60))
        second = save(
            self.store,
            map_id=1134,
            instance_id=17,
            region_id=self.region_id,
            payload=second_payload,
        )
        self.assertEqual(second["weather"], "STORM")
        self.assertEqual(second["native_payload"], second_payload)
        self.assertEqual(second["revision"], 2)
        self.assertEqual(
            context(self.store, self.character, x=self.x, y=self.y, z=self.z)[
                "weather"
            ],
            "STORM",
        )
        other_instance = dict(self.character, instance_id=18)
        self.assertEqual(
            context(self.store, other_instance, x=self.x, y=self.y, z=self.z)[
                "weather"
            ],
            "ABSENT",
        )

    def test_context_rejects_row_with_weather_inconsistent_with_native_payload(self):
        self.add_weather(1134, 17, self.region_id, "LIGHT", self.payload(3))
        with self.assertRaisesRegex(ValueError, "Inconsistent authoritative"):
            context(
                self.store,
                self.character,
                x=self.x,
                y=self.y,
                z=self.z,
            )

    def test_migration_seed_resolves_only_its_captured_native_territory(self):
        character = {"map_id": 1134, "instance_id": 0}
        resolved = context(
            self.store,
            character,
            x=-39,
            y=-72,
            z=47,
        )
        self.assertEqual(resolved["region_id"], 79301)
        self.assertEqual(resolved["weather"], "LIGHT")
        self.assertEqual(decode(resolved["native_payload"])["native_identity"], 79301)
        self.assertEqual(decode(resolved["native_payload"])["weather"], "LIGHT")


if __name__ == "__main__":
    unittest.main()
