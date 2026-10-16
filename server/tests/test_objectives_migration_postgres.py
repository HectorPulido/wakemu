"""Migration 174 carries legacy earned progress and reward receipts forward."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid

from psycopg.conninfo import make_conninfo

from postgres_case import isolated_test_url


class ObjectivesLegacyMigrationPostgresTests(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("WAKFU_POSTGRES_TEST_URL"):
            self.skipTest("Isolated PostgreSQL required")
        from wakfu_server.storage.postgres import Database, migrate
        from wakfu_server.store import Store

        url = isolated_test_url()
        password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        self.admin = Database(url, password_file=password_file)
        self.addCleanup(self.admin.close)
        self.schema = "case_" + uuid.uuid4().hex
        with self.admin.connection() as db:
            db.execute(f"CREATE SCHEMA {self.schema}")
        self.addCleanup(self.drop_schema)
        self.database_url = make_conninfo(url, options=f"-c search_path={self.schema}")
        migrations = Path(
            os.environ.get(
                "WAKFU_MIGRATIONS_TEST_DIR",
                Path(__file__).resolve().parents[1] / "migrations",
            )
        )
        self.pre174 = tempfile.TemporaryDirectory(prefix="wakfu-pre174-")
        self.addCleanup(self.pre174.cleanup)
        for path in migrations.glob("*.sql"):
            if path.name[:3].isdigit() and int(path.name[:3]) < 174:
                shutil.copyfile(path, Path(self.pre174.name) / path.name)
        with self.admin.connection() as db:
            db.execute(f"SET LOCAL search_path TO {self.schema}")
            migrate(db, self.pre174.name)

        self.store = Store(self.database_url, password_file=password_file)
        self.addCleanup(self.store.close)
        self.account = self.store.register("objective-legacy-owner", "local-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Objective Legacy")[
            "id"
        ]
        self.earned_at = "2026-10-15 12:00:00+00"
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_custom_task_progress(character_id,task_key,definition_signature,count,completed_at,updated_at) "
                "VALUES(%s,'gobball-seeds-20',%s,20,%s,%s)",
                (self.character, "a" * 64, self.earned_at, self.earned_at),
            )
            db.execute(
                "INSERT INTO character_custom_task_events(character_id,event_key,signature,payload,created_at) "
                "VALUES(%s,'planting:12345678123456789234123456789abc',%s,%s::jsonb,%s)",
                (
                    self.character,
                    "b" * 64,
                    '{"kind":"monster_seed_planted"}',
                    self.earned_at,
                ),
            )
            db.execute(
                "INSERT INTO character_custom_task_reward_outbox(character_id,task_key,reward_index,payload,created_at,delivered_at) "
                "VALUES(%s,'gobball-seeds-20',0,%s::jsonb,%s,%s)",
                (
                    self.character,
                    '{"aeV":5,"ckl":[2021,1]}',
                    self.earned_at,
                    self.earned_at,
                ),
            )
        with self.admin.connection() as db:
            db.execute(f"SET LOCAL search_path TO {self.schema}")
            migrate(db, migrations)

    def drop_schema(self):
        with self.admin.connection() as db:
            db.execute(f"DROP SCHEMA IF EXISTS {self.schema} CASCADE")

    def test_existing_completion_event_and_delivered_reward_migrate_without_reaward(
        self,
    ):
        from wakfu_server.objectives import repository

        with self.store.connection() as db:
            progress = db.execute(
                "SELECT period_key,counters,completed_at FROM objectives_progress WHERE character_id=%s AND definition_key='gobball-seeds-20'",
                (self.character,),
            ).fetchone()
            event = db.execute(
                "SELECT processed_at,attempts,signature,payload FROM objectives_events WHERE character_id=%s AND event_key=%s",
                (self.character, "planting:12345678123456789234123456789abc"),
            ).fetchone()
            rewards = db.execute(
                "SELECT payload,delivered_at FROM objectives_rewards WHERE character_id=%s AND definition_key='gobball-seeds-20'",
                (self.character,),
            ).fetchall()
        self.assertEqual(progress["period_key"], "once")
        self.assertEqual(progress["counters"], {"count": 20})
        self.assertIsNotNone(progress["completed_at"])
        self.assertIsNotNone(event["processed_at"])
        self.assertEqual(event["attempts"], 0)
        self.assertEqual(event["signature"], "b" * 64)
        self.assertEqual(event["payload"], {"kind": "monster_seed_planted"})
        self.assertEqual(len(rewards), 1)
        self.assertEqual(rewards[0]["payload"], {"aeV": 5, "ckl": [2021, 1]})
        self.assertIsNotNone(rewards[0]["delivered_at"])
        with self.store.connection() as db:
            result = repository.process_batch(db)
            self.assertEqual(result["processed"], 0)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM objectives_rewards WHERE character_id=%s AND definition_key='gobball-seeds-20'",
                    (self.character,),
                ).fetchone()["n"],
                1,
            )

    def test_content_seed_is_namespaced_and_repeat_application_does_not_revise_content(
        self,
    ):
        migration = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "178_objectives_content.sql"
        )
        with self.store.connection() as db:
            baseline = {
                "definitions": db.execute(
                    "SELECT count(*) n FROM objectives_definitions WHERE key LIKE 'content-v1.%'"
                ).fetchone()["n"],
                "policies": db.execute(
                    "SELECT count(*) n FROM objectives_reward_policies WHERE key LIKE 'content-v1.%' OR key='weekly-ranking-v1'"
                ).fetchone()["n"],
                "revisions": db.execute(
                    "SELECT md5(string_agg(key||':'||revision::text||':'||definition::text, '|' ORDER BY key)) digest "
                    "FROM objectives_definitions WHERE key LIKE 'content-v1.%'"
                ).fetchone()["digest"],
                "legacy": db.execute(
                    "SELECT definition::text,revision FROM objectives_definitions WHERE key='gobball-kills-20'"
                ).fetchone(),
            }
        self.assertEqual((baseline["definitions"], baseline["policies"]), (265, 6))
        self.assertIsNotNone(baseline["legacy"])

        for _ in range(2):
            with self.store.connection() as db:
                db.execute(migration.read_text())
        with self.store.connection() as db:
            after = {
                "definitions": db.execute(
                    "SELECT count(*) n FROM objectives_definitions WHERE key LIKE 'content-v1.%'"
                ).fetchone()["n"],
                "policies": db.execute(
                    "SELECT count(*) n FROM objectives_reward_policies WHERE key LIKE 'content-v1.%' OR key='weekly-ranking-v1'"
                ).fetchone()["n"],
                "revisions": db.execute(
                    "SELECT md5(string_agg(key||':'||revision::text||':'||definition::text, '|' ORDER BY key)) digest "
                    "FROM objectives_definitions WHERE key LIKE 'content-v1.%'"
                ).fetchone()["digest"],
                "legacy": db.execute(
                    "SELECT definition::text,revision FROM objectives_definitions WHERE key='gobball-kills-20'"
                ).fetchone(),
            }
        self.assertEqual(after, baseline)


if __name__ == "__main__":
    unittest.main()
