import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import territory_weather as weather
from wakfu_server import territory_weather_forecast as forecast
from wakfu_server import territory_weather_simulation as simulation


POLICY = dict(
    enabled=True,
    seed=20261011,
    day_seconds=86400,
    forecast_days=5,
    weather_weights=[60, 25, 12, 3],
    season_temperature_samples=[2, 12, 23, 12],
    temperature_variation=5,
    wind_samples=[13107, 22937, 42598, 62258],
)


class RegionalWeatherModelTests(unittest.TestCase):
    def test_predictions_match_future_current_state_and_instances_share_climate(self):
        policy = simulation.validate_policy(POLICY)
        states = [simulation.day_state(policy, 1134, 79201, day) for day in range(366)]
        self.assertEqual(
            states,
            [simulation.day_state(policy, 1134, 79201, day) for day in range(366)],
        )
        self.assertEqual(set(row["weather"] for row in states), set(weather.WEATHER))
        self.assertEqual(set(row["season"] for row in states), {0, 1, 2, 3})
        self.assertNotEqual(
            states,
            [simulation.day_state(policy, 1134, 79301, day) for day in range(366)],
        )

    def test_forecast_fields_remain_native_encodable_including_accelerated_seasons(
        self,
    ):
        policy = simulation.validate_policy(POLICY)
        for day in (-300, 0, 90, 180, 270, 100000000):
            days = [
                simulation.day_state(policy, 1134, 79201, day + offset)
                for offset in range(1, 6)
            ]
            seasons = [
                dict(
                    season=season,
                    actual_minimum_adjustment=0,
                    actual_maximum_adjustment=0,
                )
                for season in sorted({row["season"] for row in days})
            ]
            packet = forecast.encode_packet(days, seasons)
            self.assertEqual(len(forecast.decode_packet(packet)["days"]), 5)

    def test_current_temperature_wind_and_forecast_ranges_share_native_scale(self):
        policy = simulation.validate_policy(POLICY)
        for day in range(366):
            current = simulation.day_state(policy, 1134, 79201, day)
            actual = weather.decode(weather.encode_modeled_state(79201, current))
            self.assertEqual(
                actual["current_temperature"],
                (current["temperature_sample_a"] + current["temperature_sample_b"]) / 2,
            )
            self.assertEqual(
                actual["minimum_temperature"], current["temperature_sample_a"]
            )
            self.assertEqual(
                actual["maximum_temperature"], current["temperature_sample_b"]
            )
            self.assertAlmostEqual(
                actual["current_wind"], current["wind_strength_u16"] / 65535, places=7
            )
            days, seasons = simulation.forecast_policy(policy, 1134, 79201, day)
            bounds = {row["season"]: row for row in seasons}
            for row in days:
                self.assertLessEqual(
                    bounds[row["season"]]["actual_minimum_adjustment"],
                    row["temperature_sample_a"],
                )
                self.assertGreaterEqual(
                    bounds[row["season"]]["actual_maximum_adjustment"],
                    row["temperature_sample_b"],
                )

    def test_zero_weight_weather_never_occurs(self):
        policy = simulation.validate_policy(dict(POLICY, weather_weights=[0, 0, 1, 0]))
        for day in range(366):
            self.assertEqual(
                simulation.day_state(policy, 1134, 79201, day)["weather"], "HEAVY"
            )

    def test_invalid_policy_and_clock_fail_closed(self):
        for name, value in (
            ("enabled", 1),
            ("day_seconds", True),
            ("forecast_days", 256),
            ("weather_weights", [0, 0, 0, 0]),
            ("seed", -1),
            ("season_temperature_samples", [127] * 4),
            ("wind_samples", [65536] * 4),
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                simulation.validate_policy(dict(POLICY, **{name: value}))
        with self.assertRaises(ValueError):
            simulation.advance(object(), now=simulation.EPOCH.replace(tzinfo=None))


class RegionalWeatherDatabaseTests(PostgresCase):
    scope = dict(map_id=1134, instance_id=17, region_id=79201)

    def setUp(self):
        super().setUp()
        weather.materialize_local_state(self.store, **self.scope)

    def state(self):
        with self.store.connection() as db:
            return dict(
                db.execute(
                    "SELECT * FROM territory_weather WHERE map_id=%s AND instance_id=%s AND region_id=%s",
                    tuple(self.scope.values()),
                ).fetchone()
            )

    def forecast_days(self):
        with self.store.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT day_offset,weather FROM territory_weather_forecast_days "
                    "WHERE map_id=%s AND instance_id=%s AND region_id=%s ORDER BY day_offset",
                    tuple(self.scope.values()),
                )
            ]

    def test_forecast_predicts_next_day_and_restart_coalesces_without_reroll(self):
        now = simulation.EPOCH + timedelta(days=10, hours=1)
        original = self.state()["native_payload"]
        simulation.advance(self.store, now=now)
        initial = self.state()
        next_weather = self.forecast_days()[0]["weather"]
        self.assertEqual(len(self.forecast_days()), 5)
        self.assertEqual(simulation.advance(self.reopen(), now=now), [])
        self.assertEqual(self.state(), initial)
        simulation.advance(self.store, now=now + timedelta(days=1))
        self.assertEqual(self.state()["weather"], next_weather)
        simulation.advance(self.reopen(), now=now + timedelta(days=50))
        expected = simulation.day_state(POLICY, 1134, 79201, 60)["weather"]
        self.assertEqual(self.state()["weather"], expected)
        actual = weather.decode(self.state()["native_payload"])
        expected_state = simulation.day_state(POLICY, 1134, 79201, 60)
        self.assertEqual(
            actual["native_identity"], weather.decode(original)["native_identity"]
        )
        self.assertEqual(
            actual["current_temperature"],
            (
                expected_state["temperature_sample_a"]
                + expected_state["temperature_sample_b"]
            )
            / 2,
        )
        self.assertEqual(
            actual["minimum_temperature"], expected_state["temperature_sample_a"]
        )
        self.assertEqual(
            actual["maximum_temperature"], expected_state["temperature_sample_b"]
        )
        self.assertAlmostEqual(
            actual["current_wind"],
            expected_state["wind_strength_u16"] / 65535,
            places=7,
        )
        with self.store.connection() as db:
            cursor = db.execute(
                "SELECT simulated_day,forecast_version FROM territory_weather_simulation"
            ).fetchone()
        self.assertEqual((cursor["simulated_day"], cursor["forecast_version"]), (60, 3))

    def test_atomic_failure_does_not_advance_state_or_cursor(self):
        before = self.state()
        with patch.object(
            forecast, "save_policy", side_effect=RuntimeError("forecast failure")
        ):
            with self.assertRaisesRegex(RuntimeError, "forecast failure"):
                simulation.advance(
                    self.store, now=simulation.EPOCH + timedelta(days=10)
                )
        self.assertEqual(self.state(), before)
        self.assertEqual(self.forecast_days(), [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM territory_weather_simulation"
                ).fetchone()["n"],
                0,
            )

    def test_concurrent_first_contexts_create_one_forecast_version(self):
        stores = [self.reopen(), self.reopen()]
        scope = tuple(self.scope.values())
        now = simulation.EPOCH + timedelta(days=10)
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(
                workers.map(
                    lambda store: simulation.advance(store, now=now, scope=scope),
                    stores,
                )
            )
        with self.store.connection() as db:
            cursor = db.execute(
                "SELECT forecast_version FROM territory_weather_simulation"
            ).fetchone()
            count = db.execute(
                "SELECT count(*) AS n FROM territory_weather_forecast_outbox"
            ).fetchone()["n"]
        self.assertEqual(cursor["forecast_version"], 1)
        self.assertEqual(count, 1)
        self.assertLessEqual(sum(len(result) for result in results), 1)

    def test_native_snapshot_and_operator_forecast_are_preserved(self):
        now = simulation.EPOCH + timedelta(days=10)
        simulation.advance(self.store, now=now)
        original = self.state()["native_payload"]
        weather.save(self.store, **self.scope, payload=original[:-4] + bytes(4))
        state = self.state()
        self.assertEqual(self.forecast_days(), [])
        simulation.advance(self.store, now=now + timedelta(days=1))
        self.assertEqual(self.state(), state)
        # A new explicit forecast also prevents automatic ownership, even when
        # an operator removes the snapshot override separately.
        with self.store.connection() as db:
            db.execute(
                "UPDATE territory_weather_simulation SET explicit_override=false"
            )
        forecast.save_policy(
            self.store, **self.scope, policy_version=99, days=[], season_adjustments=[]
        )
        simulation.advance(self.store, now=now + timedelta(days=2))
        self.assertEqual(self.forecast_days(), [])
        self.assertEqual(self.state(), state)

    def test_configuration_refresh_and_instance_scoping(self):
        other = dict(self.scope, instance_id=18)
        weather.materialize_local_state(self.store, **other)
        now = simulation.EPOCH + timedelta(days=10)
        simulation.advance(self.store, now=now, limit=1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM territory_weather_simulation"
                ).fetchone()["n"],
                1,
            )
        simulation.advance(self.store, now=now, limit=1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{weather_weights}','[0,0,1,0]'::jsonb) WHERE name='weather_simulation'"
            )
        simulation.advance(self.store, now=now)
        self.assertEqual(self.state()["weather"], "HEAVY")
        self.assertTrue(all(row["weather"] == "HEAVY" for row in self.forecast_days()))
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT weather,instance_id FROM territory_weather WHERE map_id=1134 AND region_id=79201 ORDER BY instance_id"
            ).fetchall()
        self.assertEqual(
            [(row["instance_id"], row["weather"]) for row in rows],
            [(17, "HEAVY"), (18, "HEAVY")],
        )

    def test_first_context_bootstraps_forecast_only_for_current_region(self):
        other = dict(self.scope, region_id=79301)
        weather.materialize_local_state(self.store, **other)
        current = weather.context(
            self.store, {"map_id": 1134, "instance_id": 17}, x=-23, y=-143, z=70
        )
        self.assertEqual(current["region_id"], 79201)
        self.assertEqual(
            len(forecast.decode_packet(current["forecast_payload"])["days"]), 5
        )
        self.assertEqual(len(self.forecast_days()), 5)
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT region_id FROM territory_weather_simulation"
            ).fetchall()
        self.assertEqual([row["region_id"] for row in rows], [79201])

    def test_operator_transition_keeps_control_after_occurrence(self):
        now = simulation.EPOCH + timedelta(days=10)
        simulation.advance(self.store, now=now)
        at = simulation.EPOCH + timedelta(days=1000)
        weather.schedule_transition(
            self.store, **self.scope, transition_at=at, target_weather="STORM"
        )
        weather.advance_due(self.store, now=at + timedelta(seconds=1))
        self.assertEqual(self.state()["weather"], "STORM")
        simulation.advance(self.store, now=at + timedelta(days=1))
        self.assertEqual(self.state()["weather"], "STORM")

    def test_disabling_freezes_state_clears_owned_forecast_and_reenabling_resumes(self):
        now = simulation.EPOCH + timedelta(days=10)
        simulation.advance(self.store, now=now)
        state = self.state()
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{enabled}','false'::jsonb) WHERE name='weather_simulation'"
            )
        simulation.advance(self.store, now=now + timedelta(days=1))
        self.assertEqual(self.state(), state)
        self.assertEqual(self.forecast_days(), [])
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{enabled}','true'::jsonb) WHERE name='weather_simulation'"
            )
        simulation.advance(self.store, now=now + timedelta(days=1))
        self.assertEqual(
            self.state()["weather"],
            simulation.day_state(POLICY, 1134, 79201, 11)["weather"],
        )
        self.assertEqual(len(self.forecast_days()), 5)
