"""Economy multiplier migration preserves frozen definitions and receipts."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid

from psycopg.conninfo import make_conninfo

from postgres_case import isolated_test_url


class ObjectivesEconomyMigrationPostgresTests(unittest.TestCase):
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
        self.pre186 = tempfile.TemporaryDirectory(prefix="wakfu-pre186-")
        self.addCleanup(self.pre186.cleanup)
        for path in migrations.glob("*.sql"):
            if path.name[:3].isdigit() and int(path.name[:3]) < 186:
                shutil.copyfile(path, Path(self.pre186.name) / path.name)
        with self.admin.connection() as db:
            db.execute(f"SET LOCAL search_path TO {self.schema}")
            migrate(db, self.pre186.name)

        self.store = Store(self.database_url, password_file=password_file)
        self.addCleanup(self.store.close)
        self.account = self.store.register(
            "objective-economy-migration", "local-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Historical Reward")[
            "id"
        ]
        self.definition_key = "test.migration.pre186"
        self.policy_key = "test.policy.pre186"
        self.original_rewards = [
            {"kind": "kamas", "amount": 100},
            {"aeV": 5, "ckl": [2021, 2]},
            {"aeV": 6, "ckl": [300, 0]},
            {"kind": "random_item", "references": [2021], "quantity": 3},
            {"aeV": 2, "ckl": [77]},
            {"aeV": 3, "ckl": [88]},
        ]
        self.original_policy = {
            "bands": [
                {
                    "minimum": 1,
                    "maximum": 200,
                    "rewards": [dict(reward) for reward in self.original_rewards],
                }
            ]
        }
        with self.store.connection() as db:
            definition = {
                "key": self.definition_key,
                "title": "Frozen historical prize",
                "description": "A completed pre-multiplier entitlement.",
                "kind": "achievement",
                "enabled": True,
                "objectives": [
                    {
                        "key": "complete",
                        "event": "test.economy",
                        "filters": {},
                        "target": 1,
                    }
                ],
                "schedule": {"type": "once", "timezone": "UTC"},
                "rewards": [dict(reward) for reward in self.original_rewards],
            }
            from psycopg.types.json import Jsonb

            db.execute(
                "INSERT INTO objectives_definitions(key,definition,revision) VALUES(%s,%s,1)",
                (self.definition_key, Jsonb(definition)),
            )
            db.execute(
                "INSERT INTO objectives_reward_policies(key,policy,revision) VALUES(%s,%s,1)",
                (self.policy_key, Jsonb(self.original_policy)),
            )
            db.execute(
                "INSERT INTO objectives_progress(character_id,definition_key,period_key,definition_revision,"
                "counters,completed_at) VALUES(%s,%s,'once',1,'{\"complete\":1}'::jsonb,'2026-10-14T12:00:00Z')",
                (self.character, self.definition_key),
            )
            db.execute(
                "INSERT INTO objectives_rewards(character_id,definition_key,period_key,reward_index,payload,"
                "created_at,delivered_at) VALUES(%s,%s,'once',0,%s,'2026-10-14T12:00:00Z','2026-10-14T12:01:00Z')",
                (self.character, self.definition_key, Jsonb(self.original_rewards[0])),
            )

        migration186 = migrations / "186_objectives_economy_and_limits.sql"
        with self.store.connection() as db:
            db.execute(migration186.read_text())

    def drop_schema(self):
        with self.admin.connection() as db:
            db.execute(f"DROP SCHEMA IF EXISTS {self.schema} CASCADE")

    def test_multiplier_scales_only_economy_fields_and_versions_historic_data_once(
        self,
    ):
        from psycopg.types.json import Jsonb

        migration186 = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "186_objectives_economy_and_limits.sql"
        )
        expected_rewards = [
            {"kind": "kamas", "amount": 1000},
            {"aeV": 5, "ckl": [2021, 20]},
            {"aeV": 6, "ckl": [3000, 0]},
            {"kind": "random_item", "references": [2021], "quantity": 30},
            {"aeV": 2, "ckl": [77]},
            {"aeV": 3, "ckl": [88]},
        ]
        with self.store.connection() as db:
            definition = db.execute(
                "SELECT definition,revision FROM objectives_definitions WHERE key=%s",
                (self.definition_key,),
            ).fetchone()
            policy = db.execute(
                "SELECT policy,revision FROM objectives_reward_policies WHERE key=%s",
                (self.policy_key,),
            ).fetchone()
            definition_versions = db.execute(
                "SELECT revision,definition->'rewards' rewards FROM objectives_definition_versions WHERE key=%s ORDER BY revision",
                (self.definition_key,),
            ).fetchall()
            policy_versions = db.execute(
                "SELECT revision,policy FROM objectives_reward_policy_versions WHERE key=%s ORDER BY revision",
                (self.policy_key,),
            ).fetchall()
            historical = db.execute(
                "SELECT payload,delivered_at FROM objectives_rewards WHERE character_id=%s AND definition_key=%s",
                (self.character, self.definition_key),
            ).fetchall()
            progress = db.execute(
                "SELECT completed_at,counters FROM objectives_progress WHERE character_id=%s AND definition_key=%s",
                (self.character, self.definition_key),
            ).fetchone()
            audit_count = db.execute(
                "SELECT count(*) n FROM objectives_reward_policy_audit WHERE policy_key=%s",
                (self.policy_key,),
            ).fetchone()["n"]
            self.assertEqual(
                db.execute(
                    "SELECT value FROM settings WHERE name='objectives_assignment_counts'"
                ).fetchone()["value"],
                {"daily": 2, "weekly": 6, "mission": 2},
            )

        self.assertEqual(definition["revision"], 2)
        self.assertEqual(definition["definition"]["rewards"], expected_rewards)
        self.assertEqual(policy["revision"], 2)
        self.assertEqual(policy["policy"]["bands"][0]["rewards"], expected_rewards)
        self.assertEqual([row["revision"] for row in definition_versions], [1, 2])
        self.assertEqual(definition_versions[0]["rewards"], self.original_rewards)
        self.assertEqual(definition_versions[1]["rewards"], expected_rewards)
        self.assertEqual([row["revision"] for row in policy_versions], [1, 2])
        self.assertEqual(policy_versions[0]["policy"], self.original_policy)
        self.assertEqual(
            policy_versions[1]["policy"]["bands"][0]["rewards"], expected_rewards
        )
        self.assertEqual(
            historical,
            [
                {
                    "payload": self.original_rewards[0],
                    "delivered_at": historical[0]["delivered_at"],
                }
            ],
        )
        self.assertIsNotNone(historical[0]["delivered_at"])
        self.assertEqual(progress["counters"], {"complete": 1})
        self.assertIsNotNone(progress["completed_at"])

        # Reapplying the migration must not turn the amounts into x100 or
        # append another version/audit row, and completed receipts stay frozen.
        with self.store.connection() as db:
            db.execute(migration186.read_text())
            after_definition = db.execute(
                "SELECT definition,revision FROM objectives_definitions WHERE key=%s",
                (self.definition_key,),
            ).fetchone()
            after_policy = db.execute(
                "SELECT policy,revision FROM objectives_reward_policies WHERE key=%s",
                (self.policy_key,),
            ).fetchone()
            after_audit = db.execute(
                "SELECT count(*) n FROM objectives_reward_policy_audit WHERE policy_key=%s",
                (self.policy_key,),
            ).fetchone()["n"]
            after_reward = db.execute(
                "SELECT payload,delivered_at FROM objectives_rewards WHERE character_id=%s AND definition_key=%s",
                (self.character, self.definition_key),
            ).fetchone()
        self.assertEqual(after_definition, definition)
        self.assertEqual(after_policy, policy)
        self.assertEqual(after_audit, audit_count)
        self.assertEqual(after_reward, historical[0])


if __name__ == "__main__":
    unittest.main()
