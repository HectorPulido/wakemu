"""Assignment quota increases append without rerolling a frozen period."""
from datetime import datetime, timedelta, timezone
import unittest

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.objectives import assignments, repository, schedules


class ObjectivesAssignmentQuotaPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.at = datetime.now(timezone.utc)
        self.account = self.store.register("assignment-quota-owner", "local-password")[
            "id"
        ]
        self.main = self.store.create_character(self.account, "Quota Main")["id"]
        self.generation = self.store.begin_session(self.account, ttl=7200)
        self.store.select_character(self.account, self.generation, self.main)
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=20 WHERE id=%s", (self.main,))
            db.execute(
                "UPDATE settings SET value=%s WHERE name='objectives_assignment_counts'",
                (Jsonb({"daily": 2, "weekly": 2, "mission": 0}),),
            )
        for level_band in ((1, 50), (51, 200)):
            for index in range(8):
                self._put_weekly(level_band, index)

    def _put_weekly(self, level_band, index):
        minimum, maximum = level_band
        definition = {
            "key": f"test.assignment-quota.{minimum}.{index}",
            "title": f"Weekly quota {minimum}-{index}",
            "description": "Candidate used to test frozen-period selection.",
            "kind": "recurring",
            "enabled": True,
            "objectives": [
                {
                    "key": "complete",
                    "event": "test.assignment_quota",
                    "filters": {},
                    "target": 1,
                }
            ],
            "schedule": {"type": "weekly", "timezone": "America/Bogota"},
            "rewards": [],
            "level_range": {"minimum": minimum, "maximum": maximum},
        }
        with self.store.connection() as db:
            repository.put_definition(db, definition, 0)

    def test_two_weeklies_expand_to_six_from_frozen_level_without_reroll(self):
        period = schedules.period_key(
            {"type": "weekly", "timezone": "America/Bogota"}, self.at
        )
        with self.store.connection() as db:
            created = assignments.ensure_for_character(
                db, self.account, self.main, 20, at=self.at
            )
            original = {
                row["definition_key"]
                for row in db.execute(
                    "SELECT definition_key FROM objectives_assignments WHERE account_id=%s "
                    "AND group_key='weekly' AND period_key=%s",
                    (self.account, period),
                ).fetchall()
            }
        self.assertEqual(created, 4)  # two daily and two weekly
        self.assertEqual(len(original), 2)

        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=120 WHERE id=%s", (self.main,))
            db.execute(
                "UPDATE settings SET value=%s WHERE name='objectives_assignment_counts'",
                (Jsonb({"daily": 2, "weekly": 6, "mission": 0}),),
            )
            added = assignments.ensure_for_character(
                db, self.account, self.main, 120, at=self.at + timedelta(minutes=1)
            )
            current = {
                row["definition_key"]
                for row in db.execute(
                    "SELECT definition_key FROM objectives_assignments WHERE account_id=%s "
                    "AND group_key='weekly' AND period_key=%s",
                    (self.account, period),
                ).fetchall()
            }
            frozen = db.execute(
                "SELECT level FROM objectives_assignment_periods WHERE account_id=%s "
                "AND group_key='weekly' AND period_key=%s",
                (self.account, period),
            ).fetchone()["level"]
            definitions = {
                row["key"]: row["definition"]
                for row in db.execute(
                    "SELECT key,definition FROM objectives_definitions WHERE key=ANY(%s::text[])",
                    (sorted(current),),
                ).fetchall()
            }
            daily_count = db.execute(
                "SELECT count(*) n FROM objectives_assignments WHERE account_id=%s "
                "AND group_key='daily' AND period_key=%s",
                (
                    self.account,
                    schedules.period_key(
                        {"type": "daily", "timezone": "America/Bogota"}, self.at
                    ),
                ),
            ).fetchone()["n"]
            replay = assignments.ensure_for_character(
                db, self.account, self.main, 120, at=self.at + timedelta(minutes=2)
            )
            after_replay = {
                row["definition_key"]
                for row in db.execute(
                    "SELECT definition_key FROM objectives_assignments WHERE account_id=%s "
                    "AND group_key='weekly' AND period_key=%s",
                    (self.account, period),
                ).fetchall()
            }

        self.assertEqual(added, 4)
        self.assertEqual(len(current), 6)
        self.assertTrue(original <= current)
        self.assertEqual(frozen, 20)
        self.assertEqual(daily_count, 2)
        self.assertTrue(
            all(
                definition.get("level_range", {"minimum": 1, "maximum": 200})["minimum"]
                <= 20
                <= definition.get("level_range", {"minimum": 1, "maximum": 200})[
                    "maximum"
                ]
                for definition in definitions.values()
            )
        )
        self.assertEqual(replay, 0)
        self.assertEqual(after_replay, current)

        next_period_at = self.at + timedelta(days=7)
        next_period = schedules.period_key(
            {"type": "weekly", "timezone": "America/Bogota"}, next_period_at
        )
        with self.store.connection() as db:
            future_created = assignments.ensure_for_character(
                db, self.account, self.main, 120, at=next_period_at
            )
            future = db.execute(
                "SELECT count(*) n FROM objectives_assignments WHERE account_id=%s "
                "AND group_key='weekly' AND period_key=%s",
                (self.account, next_period),
            ).fetchone()["n"]
            future_level = db.execute(
                "SELECT level FROM objectives_assignment_periods WHERE account_id=%s "
                "AND group_key='weekly' AND period_key=%s",
                (self.account, next_period),
            ).fetchone()["level"]
        self.assertEqual(future_created, 8)  # two daily plus six weekly
        self.assertEqual((future, future_level), (6, 120))


if __name__ == "__main__":
    unittest.main()
