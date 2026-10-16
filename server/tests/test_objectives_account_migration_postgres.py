"""Migration 182 merges historical character progress without duplicate delivery."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid

from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

from postgres_case import isolated_test_url


class ObjectivesAccountMigrationPostgresTests(unittest.TestCase):
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
        self.pre182 = tempfile.TemporaryDirectory(prefix="wakfu-pre182-")
        self.addCleanup(self.pre182.cleanup)
        for path in migrations.glob("*.sql"):
            if path.name[:3].isdigit() and int(path.name[:3]) < 182:
                shutil.copyfile(path, Path(self.pre182.name) / path.name)
        with self.admin.connection() as db:
            db.execute(f"SET LOCAL search_path TO {self.schema}")
            migrate(db, self.pre182.name)
        self.store = Store(self.database_url, password_file=password_file)
        self.addCleanup(self.store.close)
        self.account = self.store.register("account-migration-owner", "local-password")[
            "id"
        ]
        self.main = self.store.create_character(self.account, "Migration Main")["id"]
        self.hero = self.store.create_character(self.account, "Migration Hero")["id"]
        self._seed_pre182_state()
        with self.admin.connection() as db:
            db.execute(f"SET LOCAL search_path TO {self.schema}")
            migrate(db, migrations)

    def drop_schema(self):
        with self.admin.connection() as db:
            db.execute(f"DROP SCHEMA IF EXISTS {self.schema} CASCADE")

    def _seed_pre182_state(self):
        once = {
            "key": "migration.account.once",
            "title": "Historical completion",
            "description": "Preserve a delivered reward while merging heroes.",
            "kind": "achievement",
            "enabled": True,
            "scope": "character",
            "objectives": [
                {"key": "count", "event": "migration_fact", "filters": {}, "target": 3}
            ],
            "schedule": {"type": "once", "timezone": "UTC"},
            "rewards": [],
        }
        daily = {
            "key": "migration.account.daily",
            "title": "Historical daily",
            "description": "Frozen pending event.",
            "kind": "daily",
            "enabled": True,
            "scope": "character",
            "objectives": [
                {
                    "key": "wins",
                    "event": "combat_completed",
                    "filters": {"fight_kind": "pvp", "won": True},
                    "target": 5,
                }
            ],
            "schedule": {"type": "daily", "timezone": "America/Bogota"},
            "rewards": [],
        }
        with self.store.connection() as db:
            for definition in (once, daily):
                db.execute(
                    "INSERT INTO objectives_definitions(key,definition,revision) VALUES(%s,%s,1)",
                    (definition["key"], Jsonb(definition)),
                )
            db.execute(
                "INSERT INTO objectives_progress(character_id,definition_key,period_key,definition_revision,counters,completed_at,updated_at) "
                "VALUES(%s,'migration.account.once','once',1,'{\"count\":3}'::jsonb,'2026-10-14T10:00:00Z','2026-10-14T10:00:00Z'),"
                "(%s,'migration.account.once','once',1,'{\"count\":4}'::jsonb,'2026-10-15T10:00:00Z','2026-10-15T10:00:00Z'),"
                "(%s,'migration.account.daily','2026-10-15',1,'{\"wins\":1}'::jsonb,NULL,'2026-10-14T10:00:00Z'),"
                "(%s,'migration.account.daily','2026-10-15',1,'{\"wins\":3}'::jsonb,NULL,'2026-10-15T10:00:00Z')",
                (self.main, self.hero, self.main, self.hero),
            )
            db.execute(
                "INSERT INTO objectives_rewards(character_id,definition_key,period_key,reward_index,payload,created_at,delivered_at) "
                "VALUES(%s,'migration.account.once','once',0,'{\"kind\":\"kamas\",\"amount\":77}'::jsonb,'2026-10-14T10:00:00Z','2026-10-14T10:01:00Z'),"
                "(%s,'migration.account.once','once',0,'{\"kind\":\"kamas\",\"amount\":88}'::jsonb,'2026-10-14T10:00:00Z',NULL)",
                (self.main, self.hero),
            )
            # A processed historical source must not be credited a second time
            # when another hero's copy arrives after the migration.
            db.execute(
                "INSERT INTO objectives_events(account_id,character_id,event_key,payload,signature,occurred_at,processed_at,definitions,character_level,reward_policies) "
                "VALUES(%s,%s,'old-fight-main','{\"kind\":\"combat_completed\",\"fight_kind\":\"pvp\",\"won\":true,\"fight_id\":901}'::jsonb,%s,'2026-10-15T12:00:00Z','2026-10-15T12:00:01Z','[]'::jsonb,10,'{}'::jsonb)",
                (self.account, self.main, "a" * 64),
            )
            # This event freezes the old revision and belongs to the daily
            # objective; migration must change ownership without rewriting it.
            db.execute(
                "INSERT INTO objectives_events(account_id,character_id,event_key,payload,signature,occurred_at,definitions,character_level,reward_policies) "
                'VALUES(%s,%s,\'pending-fight-hero\',\'{"kind":"combat_completed","fight_kind":"pvp","won":true,"fight_id":902}\'::jsonb,%s,\'2026-10-15T13:00:00Z\',\'[{"key":"migration.account.daily","revision":1}]\'::jsonb,10,\'{}\'::jsonb)',
                (self.account, self.hero, "b" * 64),
            )

    def test_merge_prefers_delivered_beneficiary_preserves_receipt_and_processes_frozen_event(
        self,
    ):
        from wakfu_server.objectives import repository

        with self.store.connection() as db:
            once = db.execute(
                "SELECT * FROM objectives_account_progress WHERE account_id=%s AND definition_key='migration.account.once' AND period_key='once'",
                (self.account,),
            ).fetchone()
            daily = db.execute(
                "SELECT * FROM objectives_account_progress WHERE account_id=%s AND definition_key='migration.account.daily' AND period_key='2026-10-15'",
                (self.account,),
            ).fetchone()
            saved_definition = db.execute(
                "SELECT definition,revision FROM objectives_definitions WHERE key='migration.account.daily'"
            ).fetchone()
            delivered = db.execute(
                "SELECT character_id,payload,delivered_at FROM objectives_rewards WHERE definition_key='migration.account.once'"
            ).fetchall()
            suppressed = db.execute(
                "SELECT count(*) n FROM objectives_account_migration_audit WHERE category='suppressed_duplicate_pending_reward'"
            ).fetchone()["n"]
            source = db.execute(
                "SELECT count(*) n FROM objectives_account_sources WHERE account_id=%s AND source_key='combat_completed:fight:901'",
                (self.account,),
            ).fetchone()["n"]
        self.assertEqual(once["counters"], {"count": 4})
        self.assertEqual(once["reward_character_id"], self.main)
        self.assertEqual(daily["counters"], {"wins": 3})
        self.assertEqual(saved_definition["definition"]["scope"], "account")
        self.assertEqual(saved_definition["revision"], 2)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(
            (
                delivered[0]["character_id"],
                delivered[0]["payload"],
                delivered[0]["delivered_at"] is not None,
            ),
            (self.main, {"kind": "kamas", "amount": 77}, True),
        )
        self.assertEqual(suppressed, 1)
        self.assertEqual(source, 1)

        with self.store.connection() as db:
            duplicate = repository.enqueue(
                db,
                self.account,
                self.hero,
                "same-old-fight-through-hero",
                {
                    "kind": "combat_completed",
                    "fight_kind": "pvp",
                    "won": True,
                    "fight_id": 901,
                },
                datetime_from_iso("2026-10-15T12:00:02+00:00"),
            )
            self.assertFalse(duplicate["replayed"])
            pending = db.execute(
                "SELECT definitions FROM objectives_events WHERE event_key='pending-fight-hero'"
            ).fetchone()["definitions"]
            self.assertEqual(
                pending, [{"key": "migration.account.daily", "revision": 1}]
            )
            result = repository.process_batch(db)
            self.assertEqual((result["processed"], result["failed"]), (2, 0), result)
            rows = db.execute(
                "SELECT counters FROM objectives_account_progress WHERE account_id=%s AND definition_key='migration.account.daily' AND period_key='2026-10-15'",
                (self.account,),
            ).fetchall()
            source_count = db.execute(
                "SELECT count(*) n FROM objectives_account_sources WHERE account_id=%s AND source_key='combat_completed:fight:901'",
                (self.account,),
            ).fetchone()["n"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["counters"], {"wins": 4})
        self.assertEqual(source_count, 1)


def datetime_from_iso(value):
    from datetime import datetime

    return datetime.fromisoformat(value)


if __name__ == "__main__":
    unittest.main()
