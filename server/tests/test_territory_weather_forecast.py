import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from psycopg.errors import CheckViolation
from postgres_case import PostgresCase
from wakfu_server.territory_weather_forecast import (
    decode_packet,
    encode_body,
    encode_packet,
    packet_for_territory,
    pending_publications,
    publish_pending,
    publish_to_world,
    save_policy,
)


class TerritoryWeatherForecastCodecTests(unittest.TestCase):
    def setUp(self):
        self.days = [
            {
                "season": 1,
                "temperature_sample_a": -8,
                "temperature_sample_b": 12,
                "wind_strength_u16": 0x1234,
                "weather": "HEAVY",
                "temperature_adjustment_sample": -3,
                "signed_weather_modifier_i16": -12345,
            }
        ]
        self.seasons = [
            {
                "season": 1,
                "actual_minimum_adjustment": -5,
                "actual_maximum_adjustment": 8,
            }
        ]

    def test_native_13895_golden_layout(self):
        # Independently transcribed from bRV.fe and cBl.dp bytecode.
        expected = bytes.fromhex(
            "0014" "01" "01f80c123400000002fdcfc7" "01" "01fb08" "000000"
        )
        self.assertEqual(encode_packet(self.days, self.seasons), expected)
        self.assertEqual(encode_body(self.days, self.seasons), expected[2:])
        self.assertEqual(
            decode_packet(expected),
            {
                "days": [{"day_offset": 1, **self.days[0]}],
                "season_adjustments": self.seasons,
            },
        )

    def test_native_wire_boundaries_and_empty_clear_policy(self):
        row = dict(self.days[0])
        row.update(
            season=3,
            temperature_sample_a=-128,
            temperature_sample_b=127,
            wind_strength_u16=65535,
            weather="STORM",
            temperature_adjustment_sample=127,
            signed_weather_modifier_i16=-32768,
        )
        season = {
            "season": 3,
            "actual_minimum_adjustment": -128,
            "actual_maximum_adjustment": 127,
        }
        packet = encode_packet([row], [season])
        decoded = decode_packet(packet)
        self.assertEqual(decoded["days"][0]["signed_weather_modifier_i16"], -32768)
        self.assertEqual(decoded["days"][0]["wind_strength_u16"], 65535)
        self.assertEqual(
            encode_packet([], []), b"\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00"
        )
        self.assertEqual(
            decode_packet(encode_packet([], [])),
            {
                "days": [],
                "season_adjustments": [],
            },
        )

    def test_invalid_enums_ranges_duplicates_and_truncation_fail_closed(self):
        invalid = [
            ({**self.days[0], "season": True}, self.seasons),
            ({**self.days[0], "weather": "CLEAR"}, self.seasons),
            ({**self.days[0], "temperature_sample_a": 128}, self.seasons),
            ({**self.days[0], "wind_strength_u16": 65536}, self.seasons),
            ({**self.days[0], "signed_weather_modifier_i16": 32768}, self.seasons),
            (self.days[0], []),
        ]
        for day, seasons in invalid:
            with self.subTest(day=day, seasons=seasons), self.assertRaises(ValueError):
                encode_packet([day], seasons)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            encode_packet(self.days, self.seasons * 2)
        packet = encode_packet(self.days, self.seasons)
        negative_weather_id = bytearray(packet)
        negative_weather_id[2 + 1 + 5 : 2 + 1 + 9] = b"\xff\xff\xff\xff"
        for malformed in (
            packet[:-1],
            packet + b"x",
            packet[:1],
            b"\x00\xff\x01",
            b"\x00\x01\x01",
            b"\x00\x0e\x01\x00" + b"\x00" * 12,
            bytes(negative_weather_id),
        ):
            with self.subTest(malformed=malformed.hex()), self.assertRaises(ValueError):
                decode_packet(malformed)


class TerritoryWeatherForecastStoreTests(PostgresCase):
    map_id = 1134
    region_id = 79201
    instance_id = 17

    @staticmethod
    def sample_day(weather="HEAVY"):
        return {
            "season": 1,
            "temperature_sample_a": -8,
            "temperature_sample_b": 12,
            "wind_strength_u16": 0x1234,
            "weather": weather,
            "temperature_adjustment_sample": -3,
            "signed_weather_modifier_i16": -12345,
        }

    @staticmethod
    def sample_season():
        return {
            "season": 1,
            "actual_minimum_adjustment": -5,
            "actual_maximum_adjustment": 8,
        }

    def save(self, version, *, instance_id=None, day=None):
        return save_policy(
            self.store,
            map_id=self.map_id,
            instance_id=self.instance_id if instance_id is None else instance_id,
            region_id=self.region_id,
            policy_version=version,
            days=[] if day is None else [day],
            season_adjustments=[] if day is None else [self.sample_season()],
        )

    def test_policy_is_instance_scoped_and_survives_reopen(self):
        self.assertEqual(
            packet_for_territory(
                self.store,
                map_id=self.map_id,
                instance_id=self.instance_id,
                region_id=self.region_id,
            ),
            encode_packet([], []),
        )
        saved = self.save(1, day=self.sample_day())
        self.assertEqual((saved["days"], saved["seasons"]), (1, 1))
        packet = packet_for_territory(
            self.store,
            map_id=self.map_id,
            instance_id=self.instance_id,
            region_id=self.region_id,
        )
        self.assertEqual(decode_packet(packet)["days"][0]["weather"], "HEAVY")
        self.assertEqual(
            packet_for_territory(
                self.store,
                map_id=self.map_id,
                instance_id=18,
                region_id=self.region_id,
            ),
            encode_packet([], []),
        )
        reopened = self.reopen()
        self.assertEqual(
            packet_for_territory(
                reopened,
                map_id=self.map_id,
                instance_id=self.instance_id,
                region_id=self.region_id,
            ),
            packet,
        )
        with reopened.connection() as db:
            row = db.execute(
                "SELECT temperature_sample_a,wind_strength_u16 "
                "FROM territory_weather_forecast_days WHERE map_id=%s "
                "AND instance_id=%s AND region_id=%s",
                (self.map_id, self.instance_id, self.region_id),
            ).fetchone()
        self.assertEqual(
            (row["temperature_sample_a"], row["wind_strength_u16"]), (-8, 0x1234)
        )

    def test_empty_replacement_clears_old_native_forecast(self):
        self.save(1, day=self.sample_day())
        self.save(2)
        self.assertEqual(
            packet_for_territory(
                self.store,
                map_id=self.map_id,
                instance_id=self.instance_id,
                region_id=self.region_id,
            ),
            encode_packet([], []),
        )
        with self.store.connection() as db:
            header = db.execute(
                "SELECT policy_version FROM territory_weather_forecast_policy "
                "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
                (self.map_id, self.instance_id, self.region_id),
            ).fetchone()
            days = db.execute(
                "SELECT count(*) AS n FROM territory_weather_forecast_days "
                "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
                (self.map_id, self.instance_id, self.region_id),
            ).fetchone()["n"]
        self.assertEqual(header["policy_version"], 2)
        self.assertEqual(days, 0)

    def test_invalid_policy_and_nonmonotonic_version_do_not_mutate_current_state(self):
        self.save(1, day=self.sample_day("LIGHT"))
        with self.assertRaises(ValueError):
            self.save(2, day={**self.sample_day(), "wind_strength_u16": True})
        with self.assertRaises(ValueError):
            self.save(1, day=self.sample_day("STORM"))
        self.assertEqual(
            decode_packet(
                packet_for_territory(
                    self.store,
                    map_id=self.map_id,
                    instance_id=self.instance_id,
                    region_id=self.region_id,
                )
            )["days"][0]["weather"],
            "LIGHT",
        )
        with self.assertRaises(ValueError):
            save_policy(
                self.store,
                map_id=self.map_id,
                instance_id=self.instance_id,
                region_id=999999,
                policy_version=1,
                days=[],
                season_adjustments=[],
            )

    def test_concurrent_first_writes_keep_the_highest_policy_version(self):
        barrier = Barrier(2)

        def save(version):
            barrier.wait(timeout=5)
            try:
                self.save(version)
                return version
            except ValueError:
                return "stale"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, (1, 2)))
        self.assertEqual(len(results), 2)
        self.assertEqual(
            set(results), {1, 2} if "stale" not in results else {2, "stale"}
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT policy_version FROM territory_weather_forecast_policy "
                "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
                (self.map_id, self.instance_id, self.region_id),
            ).fetchone()
        self.assertEqual(row["policy_version"], 2)

    def test_outbox_coalesces_superseded_versions_and_retries_failed_send(self):
        self.save(1, day=self.sample_day("LIGHT"))
        self.save(2, day=self.sample_day("HEAVY"))
        current = dict(
            map_id=self.map_id,
            instance_id=self.instance_id,
            region_id=self.region_id,
            policy_version=2,
        )
        self.assertEqual(pending_publications(self.store), [current])
        with self.assertRaisesRegex(OSError, "peer unavailable"):
            publish_pending(
                self.store,
                lambda _event: (_ for _ in ()).throw(OSError("peer unavailable")),
            )
        self.assertEqual(pending_publications(self.store), [current])
        sent = []
        self.assertEqual(publish_pending(self.store, sent.append), 1)
        self.assertEqual(sent, [current])
        self.assertEqual(publish_pending(self.store, sent.append), 0)
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT policy_version,published_at IS NOT NULL AS published,"
                "superseded_at IS NOT NULL AS superseded "
                "FROM territory_weather_forecast_outbox WHERE map_id=%s "
                "AND instance_id=%s AND region_id=%s ORDER BY policy_version",
                (self.map_id, self.instance_id, self.region_id),
            ).fetchall()
        self.assertEqual(
            [dict(row) for row in rows],
            [
                {"policy_version": 1, "published": False, "superseded": True},
                {"policy_version": 2, "published": True, "superseded": False},
            ],
        )

    def test_world_publication_checks_region_instance_and_current_lease(self):
        self.save(1)
        players = [
            {"id": 1, "map_id": 1134, "instance_id": 17, "x": -72, "y": -126},
            {"id": 2, "map_id": 1134, "instance_id": 17, "x": -54, "y": 54},
            {"id": 3, "map_id": 1134, "instance_id": 18, "x": -72, "y": -126},
            {"id": 4, "map_id": 1135, "instance_id": 17, "x": -72, "y": -126},
        ]

        class FakeWorld:
            sent = []

            def snapshot(self):
                return [dict(player) for player in players]

            def live_identity(self, *, character_id):
                player = next(row for row in players if row["id"] == character_id)
                if character_id == 1:
                    return None
                return character_id + 100, dict(player)

            def send_to(self, character_id, generation, opcode, body):
                self.sent.append((character_id, generation, opcode, body))
                return True

        world = FakeWorld()
        event = dict(map_id=1134, instance_id=17, region_id=79201, policy_version=1)
        self.assertEqual(publish_to_world(self.store, world, event), 0)
        self.assertEqual(world.sent, [])
        players.append(
            {"id": 5, "map_id": 1134, "instance_id": 17, "x": -72, "y": -126}
        )
        self.assertEqual(publish_to_world(self.store, world, event), 1)
        self.assertEqual([row[:3] for row in world.sent], [(5, 105, 13895)])
        self.assertEqual(world.sent[0][3], encode_packet([], []))

    def test_database_constraints_reject_invalid_wire_domain_values(self):
        self.save(1)
        with self.assertRaises(CheckViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO territory_weather_forecast_days"
                    "(map_id,instance_id,region_id,day_offset,season,"
                    "temperature_sample_a,temperature_sample_b,wind_strength_u16,"
                    "weather,temperature_adjustment_sample,signed_weather_modifier_i16) "
                    "VALUES(%s,%s,%s,1,1,0,0,65536,'LIGHT',0,0)",
                    (self.map_id, self.instance_id, self.region_id),
                )


if __name__ == "__main__":
    unittest.main()
