"""PostgreSQL regressions for migration136 selected-actor health seeding."""
from datetime import datetime, timezone
from pathlib import Path
import unittest

from postgres_case import PostgresCase
from wakfu_server import health_policy, health_store
from wakfu_server.characters import heroes


_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "136_hero_switch_health_baseline.sql"
)


class HeroSwitchHealthBaselineTests(PostgresCase):
    def setUp(self):
        super().setUp()
        sql = _MIGRATION.read_text()
        with self.store.connection() as db:
            db.execute(sql, prepare=False)
            db.execute(sql, prepare=False)
        self.account = self.store.register("hero-health-owner", "test-password")["id"]
        self.main = self.store.create_character(self.account, "Selected Main")
        self.hero = self.store.create_character(self.account, "Unselected Hero")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])

    def _regen(self, character_id):
        with self.store.connection() as db:
            return db.execute(
                "SELECT initial_hp,initial_damage,started_at,coefficient,last_at "
                "FROM character_regeneration WHERE character_id=%s",
                (character_id,),
            ).fetchone()

    def _add_hero(self):
        return heroes.add(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )

    def test_legacy_main_switch_seeds_missing_clock_and_tick_preserves_wounds(self):
        with self.store.connection() as db:
            hero = self.store.character(self.account, self.hero["id"], db)
            health_policy.apply(db, hero, hero["hp"] - 17)
        self._add_hero()
        self.assertIsNone(self._regen(self.hero["id"]))

        switched = heroes.switch_main(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )
        self.assertEqual(self.hero["id"], switched["leader"]["id"])
        seeded = self._regen(self.hero["id"])
        self.assertIsNotNone(seeded)
        self.assertEqual(17, seeded["initial_damage"])
        self.assertEqual(switched["leader"]["hp"], seeded["initial_hp"])
        ticked = health_store.tick(
            self.store,
            self.account,
            self.generation,
            self.hero["id"],
            switched["leader"]["hp"],
            now_ms=int(self.store.clock() * 1000) + 1000,
        )
        self.assertEqual(switched["leader"]["hp"], ticked["hp"])
        self.assertEqual(
            17, self.store.character(self.account, self.hero["id"])["hp_damage"]
        )

    def test_dead_hero_switch_seeds_disabled_clock_and_stays_dead(self):
        self._add_hero()
        with self.store.connection() as db:
            hero = self.store.character(self.account, self.hero["id"], db)
            health_policy.apply(db, hero, 0)
        switched = heroes.switch_main(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )
        self.assertEqual(0, switched["leader"]["hp"])
        self.assertEqual(0, self._regen(self.hero["id"])["coefficient"])
        ticked = health_store.tick(
            self.store,
            self.account,
            self.generation,
            self.hero["id"],
            0,
            now_ms=int(self.store.clock() * 1000) + 60000,
        )
        self.assertEqual(0, ticked["hp"])
        self.assertTrue(
            self.store.character(self.account, self.hero["id"])["health_dead"]
        )

    def test_switch_trigger_does_not_replace_an_existing_clock(self):
        self._add_hero()
        with self.store.connection() as db:
            hero = self.store.character(self.account, self.hero["id"], db)
            health_policy.apply(db, hero, hero["hp"] - 7)
            stamp = datetime(2024, 1, 2, tzinfo=timezone.utc)
            db.execute(
                "INSERT INTO character_regeneration"
                "(character_id,initial_hp,started_at,coefficient,last_at) "
                "VALUES(%s,%s,%s,0,%s)",
                (self.hero["id"], hero["hp"], stamp, stamp),
            )
        previous = self._regen(self.hero["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET character_id=%s WHERE account_id=%s AND generation=%s",
                (self.hero["id"], self.account, self.generation),
            )
        self.assertEqual(previous, self._regen(self.hero["id"]))

    def test_mismatched_account_does_not_seed_and_failed_switch_rolls_back_seed(self):
        foreign_account = self.store.register("hero-health-foreign", "test-password")[
            "id"
        ]
        foreign = self.store.create_character(foreign_account, "Foreign Hero")
        with self.store.connection() as db:
            constraint = db.execute(
                "SELECT conname FROM pg_constraint WHERE conrelid='sessions'::regclass "
                "AND contype='f' AND pg_get_constraintdef(oid) LIKE '%character_id%' LIMIT 1"
            ).fetchone()["conname"]
            db.execute(
                f'ALTER TABLE sessions ALTER CONSTRAINT "{constraint}" DEFERRABLE INITIALLY IMMEDIATE'
            )
        import psycopg

        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.store.connection() as db:
                db.execute(f'SET CONSTRAINTS "{constraint}" DEFERRED')
                db.execute(
                    "UPDATE sessions SET character_id=%s WHERE account_id=%s AND generation=%s",
                    (foreign["id"], self.account, self.generation),
                )
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM character_regeneration WHERE character_id=%s",
                        (foreign["id"],),
                    ).fetchone()
                )
                db.execute(f'SET CONSTRAINTS "{constraint}" IMMEDIATE')
        self.assertIsNone(self._regen(foreign["id"]))

        self._add_hero()
        with self.assertRaisesRegex(RuntimeError, "rollback after trigger"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE sessions SET character_id=%s WHERE account_id=%s AND generation=%s",
                    (self.hero["id"], self.account, self.generation),
                )
                self.assertIsNotNone(
                    db.execute(
                        "SELECT 1 FROM character_regeneration WHERE character_id=%s",
                        (self.hero["id"],),
                    ).fetchone()
                )
                raise RuntimeError("rollback after trigger")
        self.assertIsNone(self._regen(self.hero["id"]))
