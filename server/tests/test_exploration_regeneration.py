"""Proportional exploration policy with the original native health clock."""
import unittest
from protocol_codec import decode_body
from postgres_case import PostgresCase
from wakfu_server import health, health_store


class ExplorationPolicyTests(unittest.TestCase):
    def test_low_and_high_maxima_recover_within_two_minutes(self):
        for maximum in (60, 230, 2050, 2500, 100000, 2**31 - 1):
            with self.subTest(maximum=maximum):
                coefficient = health.exploration_coefficient(maximum, 1)
                self.assertGreater(coefficient, 0)
                self.assertEqual(
                    health.regenerated(1, maximum, 120000, coefficient), maximum
                )
                self.assertEqual(health.exploration_coefficient(maximum, 0), 0)
                decoded = decode_body("in", 12436, health.packet(7, 1, coefficient))
                self.assertEqual(decoded["regeneration_coefficient"], coefficient)

    def test_native_fraction_rounding_and_disabled_combat_clock_are_preserved(self):
        coefficient = health.exploration_coefficient(230, 20)
        self.assertEqual(coefficient, 8)
        self.assertEqual(health.regenerated(20, 230, 249, coefficient), 20)
        self.assertEqual(health.regenerated(20, 230, 250, coefficient), 21)
        self.assertEqual(health.regenerated(20, 230, 120000, 0), 20)
        for maximum, hp in ((True, 1), (230, True), (0, 0), (230, 231), (2**31, 1)):
            with self.assertRaises(ValueError):
                health.exploration_coefficient(maximum, hp)


class ExplorationStoreTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1
        self.account = self.store.register("exploration-regen", "local-password")["id"]
        self.generation = self.store.begin_session(self.account)
        created = self.store.create_character(self.account, "Exploration Regen")
        self.character = self.store.select_character(
            self.account, self.generation, created["id"]
        )
        self.character = health_store.initialize(
            self.store,
            self.account,
            self.generation,
            created["id"],
            exploration=True,
            now_ms=1000,
        )

    def test_policy_persistence_and_published_tick_coefficient_match_without_healing_on_entry(
        self,
    ):
        maximum = self.character["max_hp"]
        damaged = health_store.sync(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self.character["hp"],
            maximum - 10,
            now_ms=1000,
        )
        initialized = health_store.initialize(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            exploration=True,
            now_ms=1000,
        )
        self.assertEqual(initialized["hp"], damaged["hp"])
        coefficient = health.exploration_coefficient(maximum, damaged["hp"])
        fraction = health_store.tick(
            self.store,
            self.account,
            self.generation,
            damaged["id"],
            damaged["hp"],
            now_ms=1999,
        )
        self.assertEqual(fraction["hp"], damaged["hp"])
        increased = health_store.tick(
            self.store,
            self.account,
            self.generation,
            damaged["id"],
            damaged["hp"],
            now_ms=2000,
        )
        self.assertEqual(increased["hp"], damaged["hp"] + 1)
        self.assertEqual(increased["regeneration_coefficient"], coefficient)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT coefficient,started_at,initial_hp FROM character_regeneration WHERE character_id=%s",
                (damaged["id"],),
            ).fetchone()
        self.assertEqual(row["coefficient"], coefficient)
        self.assertEqual(row["initial_hp"], damaged["hp"])
        self.assertEqual(row["started_at"].timestamp(), 1)
        decoded = decode_body(
            "in",
            12436,
            health.packet(
                increased["id"], increased["hp"], increased["regeneration_coefficient"]
            ),
        )
        self.assertEqual(decoded["regeneration_coefficient"], row["coefficient"])

    def test_explicit_combat_pause_and_dead_entry_do_not_regenerate(self):
        dead = health_store.sync(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self.character["hp"],
            0,
            now_ms=1000,
        )
        health_store.initialize(
            self.store,
            self.account,
            self.generation,
            dead["id"],
            exploration=True,
            now_ms=1000,
        )
        tick = health_store.tick(
            self.store, self.account, self.generation, dead["id"], 0, now_ms=121000
        )
        self.assertEqual((tick["hp"], tick["regeneration_coefficient"]), (0, 0))
        alive = health_store.sync(
            self.store, self.account, self.generation, dead["id"], 0, 20, now_ms=122000
        )
        paused = health_store.tick(
            self.store, self.account, self.generation, alive["id"], 20, now_ms=242000
        )
        self.assertEqual((paused["hp"], paused["regeneration_coefficient"]), (20, 0))
