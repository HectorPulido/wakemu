"""Default retuning preserves custom policy and durable active-clock state."""
from pathlib import Path
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import owned_instance


class EcologyCapacityMigrationTests(PostgresCase):
    def migration(self, number):
        return next(
            (Path(__file__).resolve().parents[1] / "migrations").glob(f"{number}_*.sql")
        ).read_text()

    def test_five_minute_retune_preserves_active_clock_cycle_and_due_state(self):
        groups = PersistentGroups(self.store)
        members = [
            owned_instance(5525, 1, -id, map_id=1134, x=id, y=0, z=0)
            for id in range(1, 4)
        ]
        groups.register(1134, 0, 7, members)
        with self.store.connection() as db:
            original = db.execute(
                "SELECT value FROM settings WHERE name='monster_maturation'"
            ).fetchone()["value"]
            legacy = dict(original, interval_ms=900000, base_probability=0.25)
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_maturation'",
                (Jsonb(legacy),),
            )
            for identity, remaining, due in (
                (-1, 900000, False),
                (-2, 120000, False),
                (-3, 0, True),
            ):
                db.execute(
                    "INSERT INTO monster_maturation_timers(map_id,instance_id,monster_id,reference,remaining_ms,last_active_ms,observer_generation,due,cycle) VALUES(1134,0,%s,5525,%s,123456,'keep-generation',%s,7)",
                    (identity, remaining, due),
                )
            db.execute(self.migration(161))
            policy = db.execute(
                "SELECT value FROM settings WHERE name='monster_maturation'"
            ).fetchone()["value"]
            timers = db.execute(
                "SELECT * FROM monster_maturation_timers ORDER BY monster_id DESC"
            ).fetchall()
            self.assertEqual(
                policy, dict(legacy, interval_ms=300000, base_probability=0.10)
            )
            self.assertEqual(
                [row["remaining_ms"] for row in timers], [300000, 120000, 0]
            )
            self.assertEqual([row["due"] for row in timers], [False, False, True])
            self.assertTrue(
                all(
                    row["cycle"] == 7
                    and row["last_active_ms"] == 123456
                    and row["observer_generation"] == "keep-generation"
                    for row in timers
                )
            )
            custom = dict(policy, interval_ms=450000, base_probability=0.37)
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_maturation'",
                (Jsonb(custom),),
            )
            db.execute(self.migration(161))
            self.assertEqual(
                db.execute(
                    "SELECT value FROM settings WHERE name='monster_maturation'"
                ).fetchone()["value"],
                custom,
            )

    def test_tenfold_population_retune_preserves_individually_customized_limits(self):
        with self.store.connection() as db:
            original = db.execute(
                "SELECT value FROM settings WHERE name='monster_reproduction'"
            ).fetchone()["value"]
            for members, groups, expected_members, expected_groups in (
                (500, 100, 5000, 1000),
                (777, 100, 777, 1000),
                (500, 123, 5000, 123),
            ):
                policy = dict(
                    original, max_zone_members=members, max_zone_groups=groups
                )
                db.execute(
                    "UPDATE settings SET value=%s WHERE name='monster_reproduction'",
                    (Jsonb(policy),),
                )
                db.execute(self.migration(162))
                actual = db.execute(
                    "SELECT value FROM settings WHERE name='monster_reproduction'"
                ).fetchone()["value"]
                self.assertEqual(
                    actual,
                    dict(
                        policy,
                        max_zone_members=expected_members,
                        max_zone_groups=expected_groups,
                    ),
                )
