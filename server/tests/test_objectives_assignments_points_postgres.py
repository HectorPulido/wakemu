"""Assigned objectives and account-wide weekly points use durable receipts."""
from datetime import datetime, timedelta, timezone
import unittest

from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server.objectives import assignments, points, repository
from wakfu_server.objectives.schedules import period_key


class ObjectivesAssignmentsPointsPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "assigned-objectives-owner", "local-password"
        )["id"]
        self.main = self.store.create_character(self.account, "Assigned Main")["id"]
        self.hero = self.store.create_character(self.account, "Assigned Hero")["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main)
        self.at = datetime.now(timezone.utc)

        self.daily_period = period_key(
            {"type": "daily", "timezone": "America/Bogota"}, self.at
        )
        self.once_period = "once"
        self.daily = self._put_definition("daily", "daily", 2)
        self.mission = self._put_definition("mission", "once", 1)
        self.unassigned = self._put_definition("unassigned", "once", 1)

        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='objectives_assignment_counts'",
                (Jsonb({"daily": 0, "weekly": 0, "mission": 0}),),
            )
            self.assertEqual(
                assignments.ensure_for_character(
                    db, self.account, self.main, 1, at=self.at
                ),
                0,
            )
            for group, period in (
                ("daily", self.daily_period),
                ("mission", self.once_period),
            ):
                db.execute(
                    "INSERT INTO objectives_assignments(account_id,group_key,period_key,definition_key) VALUES(%s,%s,%s,%s)",
                    (
                        self.account,
                        group,
                        period,
                        self.daily["key"] if group == "daily" else self.mission["key"],
                    ),
                )

    def _put_definition(self, suffix, schedule_type, target):
        schedule = (
            {"type": "daily", "timezone": "America/Bogota"}
            if schedule_type == "daily"
            else {"type": "once", "timezone": "America/Bogota"}
        )
        definition = {
            "key": f"test.assigned.{suffix}",
            "title": f"Assigned {suffix}",
            "description": "Only an account assignment can earn this objective.",
            "kind": "daily" if schedule_type == "daily" else "mission",
            "enabled": True,
            "objectives": [
                {
                    "key": "complete",
                    "event": "test.assignment_fact",
                    "filters": {"qualifies": True},
                    "target": target,
                }
            ],
            "schedule": schedule,
            "rewards": [],
        }
        with self.store.connection() as db:
            return repository.put_definition(db, definition, 0)["definition"]

    def _enqueue(self, character, key, fight_id, occurred_at=None):
        with self.store.connection() as db:
            return repository.enqueue(
                db,
                self.account,
                character,
                key,
                {
                    "kind": "test.assignment_fact",
                    "qualifies": True,
                    "fight_id": fight_id,
                },
                occurred_at or self.at,
            )

    def test_only_assigned_definitions_complete_and_award_points_once_across_heroes(
        self,
    ):
        # Both heroes can contribute distinct source facts to the same account
        # assignment. A repeated fight reported by the other hero is deduped.
        self._enqueue(self.main, "daily-fight-1-main", 97001)
        self._enqueue(self.hero, "daily-fight-1-hero", 97001)
        self._enqueue(self.hero, "daily-fight-2-hero", 97002)
        self._enqueue(self.main, "unassigned-mission", 97003)
        self._enqueue(self.hero, "assigned-mission", 97004)

        with self.store.connection() as db:
            batch = repository.process_batch(db)
            self.assertEqual((batch["processed"], batch["failed"]), (5, 0), batch)
            daily = db.execute(
                "SELECT * FROM objectives_account_progress WHERE account_id=%s AND definition_key=%s AND period_key=%s",
                (self.account, self.daily["key"], self.daily_period),
            ).fetchone()
            mission = db.execute(
                "SELECT * FROM objectives_account_progress WHERE account_id=%s AND definition_key=%s AND period_key='once'",
                (self.account, self.mission["key"]),
            ).fetchone()
            unassigned_progress = db.execute(
                "SELECT 1 FROM objectives_account_progress WHERE account_id=%s AND definition_key=%s",
                (self.account, self.unassigned["key"]),
            ).fetchone()
            receipts = db.execute(
                "SELECT source_key,points,category,character_id FROM objectives_points WHERE account_id=%s ORDER BY source_key",
                (self.account,),
            ).fetchall()
            rankings = points.list_rankings(db, week=points.week_key(self.at))
            source_count = db.execute(
                "SELECT count(*) n FROM objectives_account_sources WHERE account_id=%s AND source_key='test.assignment_fact:fight:97001'",
                (self.account,),
            ).fetchone()["n"]

        self.assertEqual(daily["counters"], {"complete": 2})
        self.assertIsNotNone(daily["completed_at"])
        self.assertEqual(daily["reward_character_id"], self.hero)
        self.assertEqual(mission["counters"], {"complete": 1})
        self.assertIsNotNone(mission["completed_at"])
        self.assertIsNone(unassigned_progress)
        self.assertEqual(source_count, 1)
        self.assertEqual(len(receipts), 2)
        self.assertEqual(
            {row["source_key"] for row in receipts},
            {
                f"objective:{self.daily['key']}:{self.daily_period}",
                f"objective:{self.mission['key']}:once",
            },
        )
        self.assertEqual(
            {(row["points"], row["category"]) for row in receipts},
            {(20, "daily"), (20, "mission")},
        )
        self.assertEqual(
            [row["points"] for row in rankings if row["account_id"] == self.account],
            [40],
        )

    def test_point_source_is_idempotent_and_cannot_be_awarded_to_a_foreign_character(
        self,
    ):
        with self.store.connection() as db:
            first = points.award_configured(
                db,
                self.account,
                "manual:stable-source",
                "daily",
                character_id=self.main,
                occurred_at=self.at,
            )
            replay = points.award_configured(
                db,
                self.account,
                "manual:stable-source",
                "daily",
                character_id=self.hero,
                occurred_at=self.at,
            )
            self.assertTrue(first)
            self.assertFalse(replay)
            saved = db.execute(
                "SELECT character_id,points,category FROM objectives_points WHERE account_id=%s AND source_key='manual:stable-source'",
                (self.account,),
            ).fetchone()
            outsider = self.store.register(
                "assigned-objectives-outsider", "local-password"
            )["id"]
            outsider_character = self.store.create_character(outsider, "Outsider")["id"]
            with self.assertRaisesRegex(ValueError, "beneficiary must belong"):
                points.award_configured(
                    db,
                    self.account,
                    "manual:foreign-source",
                    "daily",
                    character_id=outsider_character,
                    occurred_at=self.at,
                )
        self.assertEqual(
            (saved["character_id"], saved["points"], saved["category"]),
            (self.main, 20, "daily"),
        )

    def test_daily_assignment_and_points_can_repeat_only_in_a_new_bogota_day(self):
        self._enqueue(self.main, "period-1-main", 97101)
        self._enqueue(self.hero, "period-1-hero", 97102)
        with self.store.connection() as db:
            first = repository.process_batch(db)
            self.assertEqual((first["processed"], first["failed"]), (2, 0), first)

        next_day = self.at + timedelta(days=1)
        while (
            period_key({"type": "daily", "timezone": "America/Bogota"}, next_day)
            == self.daily_period
        ):
            next_day += timedelta(days=1)
        next_period = period_key(
            {"type": "daily", "timezone": "America/Bogota"}, next_day
        )
        with self.store.connection() as db:
            # A fresh assignment period is created from the account's current
            # selection; the test then explicitly freezes this mission into it.
            assignments.ensure_for_character(
                db, self.account, self.main, 1, at=next_day
            )
            db.execute(
                "INSERT INTO objectives_assignments(account_id,group_key,period_key,definition_key) VALUES(%s,'daily',%s,%s)",
                (self.account, next_period, self.daily["key"]),
            )
        self._enqueue(self.main, "period-2-main", 97103, next_day)
        self._enqueue(
            self.hero, "period-2-hero", 97104, next_day + timedelta(seconds=1)
        )
        with self.store.connection() as db:
            second = repository.process_batch(db)
            rows = db.execute(
                "SELECT period_key,counters FROM objectives_account_progress WHERE account_id=%s AND definition_key=%s ORDER BY period_key",
                (self.account, self.daily["key"]),
            ).fetchall()
            receipts = db.execute(
                "SELECT source_key,points FROM objectives_points WHERE account_id=%s AND source_key LIKE %s ORDER BY source_key",
                (self.account, "objective:" + self.daily["key"] + ":%"),
            ).fetchall()
        self.assertEqual((second["processed"], second["failed"]), (2, 0), second)
        self.assertEqual(
            [(row["period_key"], row["counters"]) for row in rows],
            [
                (self.daily_period, {"complete": 2}),
                (next_period, {"complete": 2}),
            ],
        )
        self.assertEqual(len(receipts), 2)
        self.assertEqual([row["points"] for row in receipts], [20, 20])


if __name__ == "__main__":
    unittest.main()
