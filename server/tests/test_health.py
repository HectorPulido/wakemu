import unittest
from protocol_codec import decode_body
from wakfu_server import health, world_clock


class HealthTests(unittest.TestCase):
    def test_bare_client_health_matches_level_endpoints_for_every_known_breed(self):
        for breed in health.BASE_HEALTH:
            self.assertEqual(health.maximum(int(breed), 1), 60)
            self.assertEqual(health.maximum(int(breed), 200), 2050)
        for breed, level in ((17, 1), (8, 0), (8, 201)):
            with self.assertRaises(ValueError):
                health.maximum(breed, level)

    def test_regeneration_uses_java_rounding_and_caps_health(self):
        self.assertEqual(health.regenerated(50, 60, 1999, 1), 50)
        self.assertEqual(health.regenerated(50, 60, 2000, 1), 51)
        self.assertEqual(health.regenerated(50, 60, 4000, 3), 53)
        self.assertEqual(health.regenerated(50, 60, 999999, 3), 60)
        self.assertEqual(health.regenerated(50, 60, 999999, 0), 50)

    def test_health_sync_and_clock_are_verified_wire_shapes(self):
        self.assertEqual(
            {
                key: value
                for key, value in decode_body(
                    "in", 12436, health.packet(7, 2050, 3)
                ).items()
                if key in ("actor_id", "health", "regeneration_coefficient")
            },
            {"actor_id": 7, "health": 2050, "regeneration_coefficient": 3},
        )
        self.assertEqual(
            world_clock.packet(1000, 500), bytes.fromhex("00000000000005dc")
        )


class HealthStoreTests(unittest.TestCase):
    def test_owned_health_persists_and_stale_session_cannot_tick(self):
        import tempfile
        from pathlib import Path
        from wakfu_server.store import Store
        from wakfu_server import health_store

        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "db")
            account = store.register("health-test", "health-password")["id"]
            char = store.create_character(account, "Health Test", breed=8)
            generation = store.begin_session(account)
            store.select_character(account, generation, char["id"])
            with store.connection() as db:
                db.execute("UPDATE characters SET level=200 WHERE id=?", (char["id"],))
            char = health_store.initialize(
                store, account, generation, char["id"], now_ms=1000
            )
            self.assertEqual((char["hp"], char["max_hp"]), (2050, 2050))
            char = health_store.sync(
                store,
                account,
                generation,
                char["id"],
                2050,
                2040,
                coefficient=1,
                now_ms=1000,
            )
            for now, hp in (
                (2000, 2040),
                (3000, 2041),
                (4000, 2041),
                (5000, 2041),
                (7000, 2042),
            ):
                char = health_store.tick(
                    store, account, generation, char["id"], char["hp"], now_ms=now
                )
                self.assertEqual(char["hp"], hp)
            self.assertEqual(
                Store(Path(tmp) / "db").character(account, char["id"])["hp"], 2042
            )
            with self.assertRaises(ValueError):
                health_store.tick(
                    store, account, generation, char["id"], 2040, now_ms=8000
                )
            with self.assertRaises(ValueError):
                health_store.tick(
                    store, account, generation, char["id"], 2042, now_ms=6000
                )
            store.begin_session(account)
            with self.assertRaises(ValueError):
                health_store.tick(
                    store, account, generation, char["id"], 2042, now_ms=8000
                )


class ClockTests(unittest.TestCase):
    def test_client_two_hour_cycle_boundaries(self):
        for ms, expected in (
            (0, False),
            (1799999, False),
            (1800000, True),
            (5399999, True),
            (5400000, False),
            (7200000, False),
        ):
            self.assertEqual(world_clock.daytime(ms), expected)
