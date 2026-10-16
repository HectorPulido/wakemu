"""Completion chat notices are durable, account-scoped and once-only."""
from datetime import datetime, timezone
import unittest

from postgres_case import PostgresCase
from wakfu_server.objectives import notices, repository


class ObjectivesCompletionNoticesPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("objective-notices-owner", "local-password")[
            "id"
        ]
        self.main = self.store.create_character(self.account, "Notice Main")["id"]
        self.hero = self.store.create_character(self.account, "Notice Hero")["id"]
        self.generation = self.store.begin_session(self.account, ttl=7200)
        self.store.select_character(self.account, self.generation, self.main)
        self.at = datetime.now(timezone.utc)
        self.definition = {
            "key": "test.notice.arrival",
            "title": "The First Step",
            "description": "Complete one trusted game fact.",
            "kind": "achievement",
            "enabled": True,
            "objectives": [
                {"key": "complete", "event": "test.notice", "filters": {}, "target": 1}
            ],
            "schedule": {"type": "once", "timezone": "UTC"},
            "rewards": [],
        }
        with self.store.connection() as db:
            repository.put_definition(db, self.definition, 0)

    def test_normal_completion_emits_one_pending_notice_then_current_hero_receives_it_once(
        self,
    ):
        with self.store.connection() as db:
            first = repository.enqueue(
                db,
                self.account,
                self.main,
                "notice-fact-1",
                {"kind": "test.notice"},
                self.at,
            )
        self.assertFalse(first["replayed"])
        with self.store.connection() as db:
            batch = repository.process_batch(db)
            self.assertEqual((batch["processed"], batch["failed"]), (1, 0), batch)
        with self.store.connection() as db:
            stored = db.execute(
                "SELECT * FROM objectives_completion_notices WHERE account_id=%s",
                (self.account,),
            ).fetchall()
            source = "objective:test.notice.arrival:once"
            replay = repository.enqueue(
                db,
                self.account,
                self.main,
                "notice-fact-1",
                {"kind": "test.notice"},
                self.at,
            )
            processed_again = repository.process_batch(db)
        self.assertTrue(replay["replayed"])
        self.assertEqual(processed_again["processed"], 0)
        self.assertEqual(len(stored), 1)
        self.assertEqual(
            (stored[0]["source_key"], stored[0]["title"], stored[0]["points"]),
            (source, "The First Step", 10),
        )
        self.assertIsNone(stored[0]["delivered_at"])

        # The notice belongs to the account, but delivery follows only its
        # current selected World character and lease.
        self.store.select_character(self.account, self.generation, self.hero)
        wrong_character_messages = []
        with self.store.connection() as db:
            self.assertEqual(
                notices.deliver(
                    db,
                    self.account,
                    self.generation,
                    self.main,
                    wrong_character_messages.append,
                ),
                0,
            )
        self.assertEqual(wrong_character_messages, [])

        # Offline polls leave it queued. Reconnect on the hero, then deliver.
        with self.store.connection() as db:
            db.execute("DELETE FROM sessions WHERE account_id=%s", (self.account,))
            self.assertEqual(
                notices.deliver(
                    db,
                    self.account,
                    self.generation,
                    self.hero,
                    wrong_character_messages.append,
                ),
                0,
            )
        self.assertEqual(wrong_character_messages, [])
        new_generation = self.store.begin_session(self.account, ttl=7200)
        self.store.select_character(self.account, new_generation, self.hero)
        with self.store.connection() as db:
            with self.assertRaisesRegex(RuntimeError, "socket write failed"):
                notices.deliver(
                    db,
                    self.account,
                    new_generation,
                    self.hero,
                    lambda _message: (_ for _ in ()).throw(
                        RuntimeError("socket write failed")
                    ),
                )
        with self.store.connection() as db:
            still_pending = db.execute(
                "SELECT delivered_at FROM objectives_completion_notices WHERE account_id=%s",
                (self.account,),
            ).fetchone()
            delivered = notices.deliver(
                db,
                self.account,
                new_generation,
                self.hero,
                wrong_character_messages.append,
            )
            duplicate_poll = notices.deliver(
                db,
                self.account,
                new_generation,
                self.hero,
                wrong_character_messages.append,
            )
            receipt = db.execute(
                "SELECT delivered_at,delivered_character_id FROM objectives_completion_notices WHERE account_id=%s",
                (self.account,),
            ).fetchone()

        self.assertIsNone(still_pending["delivered_at"])
        self.assertEqual((delivered, duplicate_poll), (1, 0))
        self.assertEqual(
            wrong_character_messages,
            ["Objective completed: The First Step (+10 points)."],
        )
        self.assertIsNotNone(receipt["delivered_at"])
        self.assertEqual(receipt["delivered_character_id"], self.hero)


if __name__ == "__main__":
    unittest.main()
