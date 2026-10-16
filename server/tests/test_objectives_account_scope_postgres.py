"""Account-wide recurring objectives progress and reward delivery."""
from datetime import datetime, timezone
import unittest

from postgres_case import PostgresCase
from wakfu_server.objectives import catalog, repository
from wakfu_server.objectives.schedules import period_key


class ObjectivesAccountScopePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "account-objectives-owner", "local-password"
        )["id"]
        self.main = self.store.create_character(self.account, "Account Main")["id"]
        self.hero = self.store.create_character(self.account, "Account Hero")["id"]
        self.definition = {
            "key": "test.account.daily-duels",
            "title": "Win two daily duels",
            "description": "Wins from any owned hero count once per fight.",
            "kind": "pvp",
            "enabled": True,
            "objectives": [
                {
                    "key": "wins",
                    "event": "combat_completed",
                    "filters": {"fight_kind": "duel", "won": True},
                    "target": 2,
                }
            ],
            "schedule": {"type": "daily", "timezone": "America/Bogota"},
            "rewards": [{"kind": "kamas", "amount": 1200}],
        }
        with self.store.connection() as db:
            saved = repository.put_definition(db, self.definition, 0)
        self.definition = saved["definition"]

    def enqueue(self, character, event_key, fight_id, at):
        with self.store.connection() as db:
            return repository.enqueue(
                db,
                self.account,
                character,
                event_key,
                {
                    "kind": "combat_completed",
                    "fight_kind": "duel",
                    "won": True,
                    "fight_id": fight_id,
                },
                at,
            )

    def test_progress_is_shared_deduplicated_by_fight_and_paid_once_to_completing_hero(
        self,
    ):
        first = datetime(2026, 10, 15, 18, tzinfo=timezone.utc)
        self.enqueue(self.main, "duel:8001:main", 8001, first)
        # The same durable fight can be observed through several participating
        # heroes; the account source ledger admits it only once.
        self.enqueue(
            self.hero,
            "duel:8001:hero",
            8001,
            datetime(2026, 10, 15, 18, 0, 1, tzinfo=timezone.utc),
        )
        self.enqueue(
            self.hero,
            "duel:8002:hero",
            8002,
            datetime(2026, 10, 15, 18, 2, tzinfo=timezone.utc),
        )
        with self.store.connection() as db:
            result = repository.process_batch(db)
            self.assertEqual((result["processed"], result["failed"]), (3, 0), result)
            rows = db.execute(
                "SELECT * FROM objectives_account_progress WHERE account_id=%s AND definition_key=%s",
                (self.account, self.definition["key"]),
            ).fetchall()
            source_count = db.execute(
                "SELECT count(*) n FROM objectives_account_sources WHERE account_id=%s AND source_key='combat_completed:fight:8001'",
                (self.account,),
            ).fetchone()["n"]
            payout_rows = db.execute(
                "SELECT character_id,period_key,payload,delivered_at FROM objectives_rewards WHERE definition_key=%s",
                (self.definition["key"],),
            ).fetchall()
            main_projection = repository.list_progress(db, self.main)
            hero_projection = repository.list_progress(db, self.hero)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["period_key"], "2026-10-15")
        self.assertEqual(rows[0]["counters"], {"wins": 2})
        self.assertIsNotNone(rows[0]["completed_at"])
        self.assertEqual(rows[0]["reward_character_id"], self.hero)
        self.assertEqual(source_count, 1)
        self.assertEqual(len(payout_rows), 1)
        self.assertEqual(
            (payout_rows[0]["character_id"], payout_rows[0]["payload"]),
            (self.hero, {"kind": "kamas", "amount": 1200}),
        )
        for projection in (main_projection, hero_projection):
            matches = [
                row
                for row in projection
                if row["definition_key"] == self.definition["key"]
            ]
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["counters"], {"wins": 2})
            self.assertEqual(matches[0]["period_key"], "2026-10-15")

        # The next Bogota day starts a separate entitlement period.
        self.enqueue(
            self.main,
            "duel:8003:main",
            8003,
            datetime(2026, 10, 16, 5, tzinfo=timezone.utc),
        )
        with self.store.connection() as db:
            result = repository.process_batch(db)
            self.assertEqual((result["processed"], result["failed"]), (1, 0), result)
            periods = db.execute(
                "SELECT period_key,counters,completed_at FROM objectives_account_progress WHERE account_id=%s AND definition_key=%s ORDER BY period_key",
                (self.account, self.definition["key"]),
            ).fetchall()
            rewards = db.execute(
                "SELECT count(*) n FROM objectives_rewards WHERE definition_key=%s",
                (self.definition["key"],),
            ).fetchone()["n"]
        self.assertEqual(
            [
                (row["period_key"], row["counters"], row["completed_at"] is not None)
                for row in periods
            ],
            [
                ("2026-10-15", {"wins": 2}, True),
                ("2026-10-16", {"wins": 1}, False),
            ],
        )
        self.assertEqual(rewards, 1)

    def test_account_scope_is_default_and_all_recurrence_periods_are_valid(self):
        schedules = [
            {"type": "daily", "timezone": "America/Bogota"},
            {"type": "weekly", "timezone": "America/Bogota"},
            {"type": "calendar", "timezone": "America/Bogota", "month_days": ["10-15"]},
            {
                "type": "interval",
                "timezone": "America/Bogota",
                "anchor": "2026-10-15T00:00:00+00:00",
                "seconds": 3600,
            },
        ]
        for index, schedule in enumerate(schedules):
            definition = {
                **self.definition,
                "key": f"test.account.schedule-{index}",
                "schedule": schedule,
            }
            self.assertEqual(
                catalog.validate_definition(definition)["scope"], "account"
            )

        bogota_daily = schedules[0]
        self.assertEqual(
            period_key(
                bogota_daily, datetime(2026, 10, 16, 4, 59, 59, tzinfo=timezone.utc)
            ),
            "2026-10-15",
        )
        self.assertEqual(
            period_key(bogota_daily, datetime(2026, 10, 16, 5, tzinfo=timezone.utc)),
            "2026-10-16",
        )
        bogota_weekly = schedules[1]
        self.assertEqual(
            period_key(
                bogota_weekly, datetime(2026, 10, 19, 4, 59, 59, tzinfo=timezone.utc)
            ),
            "2026-10-12",
        )
        self.assertEqual(
            period_key(bogota_weekly, datetime(2026, 10, 19, 5, tzinfo=timezone.utc)),
            "2026-10-19",
        )
        self.assertEqual(
            period_key(schedules[2], datetime(2026, 10, 15, 12, tzinfo=timezone.utc)),
            "2026-10-15",
        )
        self.assertIsNone(
            period_key(schedules[2], datetime(2026, 10, 16, 12, tzinfo=timezone.utc))
        )
        self.assertEqual(
            period_key(schedules[3], datetime(2026, 10, 15, 1, tzinfo=timezone.utc)),
            "1",
        )
        self.assertEqual(
            period_key(
                schedules[3], datetime(2026, 10, 15, 1, 59, 59, tzinfo=timezone.utc)
            ),
            "1",
        )
        self.assertEqual(
            period_key(schedules[3], datetime(2026, 10, 15, 2, tzinfo=timezone.utc)),
            "2",
        )


if __name__ == "__main__":
    unittest.main()
