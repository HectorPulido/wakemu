"""Progression achievements observe authoritative account-wide milestones once."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

import psycopg
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.objectives import progression, repository


class ObjectivesAccountProgressionPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "account-progression-owner", "local-password"
        )["id"]
        self.main = self.store.create_character(self.account, "Progression Main")["id"]
        self.generation = self.store.begin_session(self.account, ttl=7200)
        self.store.select_character(self.account, self.generation, self.main)
        self.at = datetime.now(timezone.utc)

    def _observe_and_process(self):
        published = progression.observe(
            self.store, self.account, self.generation, self.main
        )
        with patch(
            "wakfu_server.objectives.reward_policies.expand",
            return_value=[{"kind": "kamas", "amount": 1000}],
        ):
            with self.store.connection() as db:
                result = repository.process_batch(db)
        return published, result

    def test_historical_levels_distinct_characters_professions_and_repoll_are_once_only(
        self,
    ):
        hero_one = self.store.create_character(self.account, "Progression Hero One")[
            "id"
        ]
        hero_two = self.store.create_character(self.account, "Progression Hero Two")[
            "id"
        ]
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=200 WHERE id=%s", (self.main,))
            db.execute("UPDATE characters SET level=199 WHERE id=%s", (hero_one,))
            db.execute("UPDATE characters SET level=199 WHERE id=%s", (hero_two,))
            db.execute(
                "INSERT INTO account_professions(account_id,profession_id,xp) VALUES(%s,40,750000) "
                "ON CONFLICT(account_id,profession_id) DO UPDATE SET xp=EXCLUDED.xp",
                (self.account,),
            )
            db.execute(
                "INSERT INTO account_professions(account_id,profession_id,xp) VALUES(%s,41,749999) "
                "ON CONFLICT(account_id,profession_id) DO UPDATE SET xp=EXCLUDED.xp",
                (self.account,),
            )
            with self.assertRaisesRegex(
                ValueError, "differs from persisted native progress"
            ):
                repository.enqueue(
                    db,
                    self.account,
                    self.main,
                    "forged-progression-count",
                    {
                        "kind": progression.CHARACTER_EVENT,
                        "minimum_level": 50,
                        "count": 1,
                    },
                )

        # Historical max level and craft progress are discovered from persisted
        # World state when the connected account is polled; they need no new XP.
        published, result = self._observe_and_process()
        self.assertGreaterEqual(
            published, 5
        )  # four character thresholds + one profession threshold
        self.assertEqual(result["failed"], 0, result)
        self.assertEqual(result["processed"], published)

        with self.store.connection() as db:
            account_rows = db.execute(
                "SELECT definition_key,counters,completed_at,reward_character_id FROM objectives_account_progress "
                "WHERE account_id=%s AND definition_key LIKE 'progression-v1.%%' ORDER BY definition_key",
                (self.account,),
            ).fetchall()
            rewards = db.execute(
                "SELECT definition_key,period_key,count(*) AS count FROM objectives_rewards "
                "WHERE definition_key LIKE 'progression-v1.%%' GROUP BY definition_key,period_key ORDER BY definition_key",
            ).fetchall()
            points_before = db.execute(
                "SELECT source_key,points FROM objectives_points WHERE account_id=%s "
                "AND source_key LIKE 'objective:progression-v1.%%' ORDER BY source_key",
                (self.account,),
            ).fetchall()
            definitions = {
                row["key"]: row["definition"]
                for row in db.execute(
                    "SELECT key,definition FROM objectives_definitions WHERE key LIKE 'progression-v1.%%'"
                ).fetchall()
            }
            profession_count = progression.native_count(
                db, self.account, progression.PROFESSION_EVENT, 100
            )

        by_key = {row["definition_key"]: row for row in account_rows}
        for threshold in (50, 100, 150, 200):
            key = f"progression-v1.characters.level.{threshold}"
            self.assertIsNotNone(by_key[key]["completed_at"], key)
            self.assertEqual(by_key[key]["counters"], {"count": 1})
        self.assertEqual(
            by_key["progression-v1.characters.level.200.count.2"]["counters"],
            {"count": 1},
        )
        self.assertEqual(
            by_key["progression-v1.characters.level.200.count.3"]["counters"],
            {"count": 1},
        )
        self.assertIsNone(
            by_key["progression-v1.characters.level.200.count.2"]["completed_at"]
        )
        self.assertEqual(profession_count, 1)
        self.assertIsNotNone(
            by_key["progression-v1.professions.level.100.count.1"]["completed_at"]
        )
        self.assertEqual(
            by_key["progression-v1.professions.level.100.count.2"]["counters"],
            {"count": 1},
        )
        self.assertNotIn("progression-v1.characters.level.245", by_key)
        self.assertEqual(
            definitions["progression-v1.characters.level.245"]["objectives"][0][
                "filters"
            ],
            {"minimum_level": 245},
        )
        self.assertTrue(all(row["count"] == 1 for row in rewards))
        self.assertEqual(len(rewards), len(points_before))

        # Repeated World polling over the same absolute state creates no new
        # event, reward or point receipt.
        self.assertEqual(
            progression.observe(self.store, self.account, self.generation, self.main), 0
        )
        with self.store.connection() as db:
            replay = repository.process_batch(db)
            rewards_after = db.execute(
                "SELECT count(*) AS count FROM objectives_rewards WHERE definition_key LIKE 'progression-v1.%%'"
            ).fetchone()["count"]
            points_after = db.execute(
                "SELECT count(*) AS count FROM objectives_points WHERE account_id=%s "
                "AND source_key LIKE 'objective:progression-v1.%%'",
                (self.account,),
            ).fetchone()["count"]
        self.assertEqual(replay["processed"], 0)
        self.assertEqual(rewards_after, len(rewards))
        self.assertEqual(points_after, len(points_before))

        # A second *distinct* 200-level character completes the two-character
        # achievement; a sub-200 hero is not counted.
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=200 WHERE id=%s", (hero_one,))
            level_counts = [
                progression.native_count(
                    db, self.account, progression.CHARACTER_EVENT, threshold
                )
                for threshold in (50, 100, 150, 200)
            ]
        published, result = self._observe_and_process()
        self.assertEqual(
            published, 1, {"native_level_counts": level_counts, "worker": result}
        )
        self.assertEqual(result["failed"], 0, result)
        with self.store.connection() as db:
            second_count = db.execute(
                "SELECT counters,completed_at FROM objectives_account_progress WHERE account_id=%s "
                "AND definition_key='progression-v1.characters.level.200.count.2'",
                (self.account,),
            ).fetchone()
            third_count = db.execute(
                "SELECT counters,completed_at FROM objectives_account_progress WHERE account_id=%s "
                "AND definition_key='progression-v1.characters.level.200.count.3'",
                (self.account,),
            ).fetchone()
        self.assertEqual(second_count["counters"], {"count": 2})
        self.assertIsNotNone(second_count["completed_at"])
        self.assertEqual(third_count["counters"], {"count": 2})
        self.assertIsNone(third_count["completed_at"])

        # A third *distinct* level-200 character completes the 3-character
        # milestone, and the earlier two-character receipt is not repeated.
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=200 WHERE id=%s", (hero_two,))
        published, result = self._observe_and_process()
        self.assertEqual(published, 1)  # only the >=200 count changed
        self.assertEqual(result["failed"], 0, result)
        with self.store.connection() as db:
            counts = {
                row["definition_key"]: row
                for row in db.execute(
                    "SELECT definition_key,counters,completed_at FROM objectives_account_progress "
                    "WHERE account_id=%s AND definition_key LIKE 'progression-v1.characters.level.200.count.%%'",
                    (self.account,),
                ).fetchall()
            }
            duplicates = db.execute(
                "SELECT definition_key,count(*) AS count FROM objectives_rewards WHERE definition_key LIKE 'progression-v1.characters.level.200.count.%%' GROUP BY definition_key",
            ).fetchall()
        for count in (2, 3):
            key = f"progression-v1.characters.level.200.count.{count}"
            self.assertEqual(counts[key]["counters"], {"count": count})
            self.assertIsNotNone(counts[key]["completed_at"])
        self.assertEqual(
            {row["definition_key"]: row["count"] for row in duplicates},
            {
                "progression-v1.characters.level.200.count.2": 1,
                "progression-v1.characters.level.200.count.3": 1,
            },
        )

        # The profession ledger is account-scoped and unique by profession id.
        # Two heroes cannot double-count one profession; a second distinct ID
        # crosses the two-profession milestone, and a third crosses three.
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO account_professions(account_id,profession_id,xp) VALUES(%s,40,750000)",
                    (self.account,),
                )
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=750000 WHERE account_id=%s AND profession_id=41",
                (self.account,),
            )
        published, result = self._observe_and_process()
        self.assertEqual(result["failed"], 0, result)
        with self.store.connection() as db:
            profession_rows = {
                row["definition_key"]: row
                for row in db.execute(
                    "SELECT definition_key,counters,completed_at FROM objectives_account_progress "
                    "WHERE account_id=%s AND definition_key LIKE 'progression-v1.professions.%%'",
                    (self.account,),
                ).fetchall()
            }
            self.assertEqual(
                progression.native_count(
                    db, self.account, progression.PROFESSION_EVENT, 100
                ),
                2,
            )
        self.assertEqual(
            profession_rows["progression-v1.professions.level.100.count.2"]["counters"],
            {"count": 2},
        )
        self.assertIsNotNone(
            profession_rows["progression-v1.professions.level.100.count.2"][
                "completed_at"
            ]
        )
        self.assertEqual(
            profession_rows["progression-v1.professions.level.100.count.3"]["counters"],
            {"count": 2},
        )
        self.assertEqual(
            progression.observe(self.store, self.account, self.generation, self.main), 0
        )

        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_professions(account_id,profession_id,xp) VALUES(%s,42,750000)",
                (self.account,),
            )
        published, result = self._observe_and_process()
        self.assertEqual(result["failed"], 0, result)
        with self.store.connection() as db:
            final = db.execute(
                "SELECT counters,completed_at FROM objectives_account_progress WHERE account_id=%s "
                "AND definition_key='progression-v1.professions.level.100.count.3'",
                (self.account,),
            ).fetchone()
            rows = db.execute(
                "SELECT r.definition_key,count(*) AS count FROM objectives_rewards r "
                "JOIN characters c ON c.id=r.character_id WHERE c.account_id=%s "
                "AND r.definition_key LIKE 'progression-v1.professions.%%' GROUP BY r.definition_key",
                (self.account,),
            ).fetchall()
        self.assertEqual(final["counters"], {"count": 3})
        self.assertIsNotNone(final["completed_at"])
        self.assertEqual({row["count"] for row in rows}, {1})
        self.assertEqual(
            progression.observe(self.store, self.account, self.generation, self.main), 0
        )

    def test_level_245_milestone_is_seeded_without_raising_native_character_cap(self):
        with self.store.connection() as db:
            definition = db.execute(
                "SELECT definition FROM objectives_definitions WHERE key='progression-v1.characters.level.245'"
            ).fetchone()["definition"]
            with self.assertRaises(psycopg.errors.CheckViolation):
                with db.transaction():
                    db.execute(
                        "UPDATE characters SET level=245 WHERE id=%s", (self.main,)
                    )
            saved = db.execute(
                "SELECT level FROM characters WHERE id=%s", (self.main,)
            ).fetchone()["level"]
        self.assertEqual(definition["objectives"][0]["filters"]["minimum_level"], 245)
        self.assertEqual(saved, 1)


if __name__ == "__main__":
    unittest.main()
