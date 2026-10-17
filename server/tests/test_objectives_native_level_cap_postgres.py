"""Level245 objective ingress persists and pays once in an isolated schema."""
from datetime import datetime, timezone
from postgres_case import PostgresCase
from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
from wakfu_server.objectives import repository


class ObjectivesNativeLevelCapPostgresTests(PostgresCase):
    def test_level245_source_fact_is_frozen_and_reward_reserved_once(self):
        self.assertEqual(MAX_CHARACTER_LEVEL, 245)
        owner = self.store.register("objective-native245-owner", "local-password")["id"]
        character = self.store.create_character(owner, "Native Level Cap")["id"]
        definition = {
            "key": "native245-objective",
            "title": "Native245 objective",
            "description": "Isolated native level source and reward receipt",
            "kind": "achievement",
            "enabled": True,
            "objectives": [
                {
                    "key": "count",
                    "event": "fixture_event",
                    "filters": {"subject": 1},
                    "target": 1,
                }
            ],
            "schedule": {"type": "once", "timezone": "UTC"},
            "rewards": [{"kind": "kamas", "amount": 17}],
        }
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=245 WHERE id=%s", (character,))
            repository.put_definition(db, definition, 0)
            args = (
                db,
                owner,
                character,
                "native245-source",
                {"kind": "fixture_event", "subject": 1},
            )
            first = repository.enqueue(
                *args, occurred_at=datetime(2026, 10, 17, tzinfo=timezone.utc)
            )
            self.assertFalse(first["replayed"])
            self.assertTrue(
                repository.enqueue(
                    *args, occurred_at=datetime(2026, 10, 17, tzinfo=timezone.utc)
                )["replayed"]
            )
            frozen = db.execute(
                "SELECT character_level,definitions FROM objectives_events WHERE id=%s",
                (first["id"],),
            ).fetchone()
            self.assertEqual(frozen["character_level"], 245)
            self.assertEqual(
                frozen["definitions"], [{"key": definition["key"], "revision": 1}]
            )
            result = repository.process_batch(db, 100)
            self.assertEqual(result["failed"], 0, result)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM objectives_rewards WHERE definition_key=%s",
                    (definition["key"],),
                ).fetchone()["n"],
                1,
            )
            repository.process_batch(db, 100)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM objectives_rewards WHERE definition_key=%s",
                    (definition["key"],),
                ).fetchone()["n"],
                1,
            )
            points = db.execute(
                "SELECT level FROM objectives_points WHERE account_id=%s AND character_id=%s",
                (owner, character),
            ).fetchall()
            self.assertTrue(points)
            self.assertTrue(all(row["level"] == 245 for row in points))
