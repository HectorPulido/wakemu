"""Upgrade the byte-exact deployed ecology migration without changing its checksum."""
from hashlib import sha256
from pathlib import Path
import shutil
import tempfile
import uuid

from postgres_case import PostgresCase
from wakfu_server.postgres import migrate


class EcologyDeliveryUpgradeTests(PostgresCase):
    def test_applied_104_upgrades_to_current_schema_and_preserves_pending_envelope(
        self,
    ):
        migrations = Path(__file__).resolve().parents[1] / "migrations"
        expected = "ca59d1cd5d2cb07e27e10a5a9897520cfbc3eac3e1e1e9a1d31c24b8779f5bad"
        self.assertEqual(
            sha256((migrations / "104_ecology_service.sql").read_bytes()).hexdigest(),
            expected,
        )
        schema = "upgrade_" + uuid.uuid4().hex
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            for path in migrations.glob("*.sql"):
                if int(path.name[:3]) <= 104:
                    shutil.copyfile(path, prefix / path.name)
            with self.store.connection() as db:
                db.execute(f"CREATE SCHEMA {schema}")
                db.execute(f"SET LOCAL search_path TO {schema}")
                self.assertEqual(migrate(db, prefix), 104)
                db.execute(
                    "INSERT INTO ecology_service_proposals(id,domain,payload,world_epoch) "
                    "VALUES('pending-before-upgrade','plants','{\"uid\":991}'::jsonb,'old-world')"
                )
                self.assertEqual(
                    db.execute(
                        "SELECT checksum FROM schema_migrations WHERE version=104"
                    ).fetchone()["checksum"],
                    expected,
                )
                applied = migrate(db, migrations)
                self.assertGreaterEqual(applied, 6)
                row = db.execute(
                    "SELECT payload,world_epoch,next_attempt_at,delivered_at "
                    "FROM ecology_service_proposals WHERE id='pending-before-upgrade'"
                ).fetchone()
                self.assertEqual(row["payload"], {"uid": 991})
                self.assertEqual(row["world_epoch"], "old-world")
                self.assertIsNone(row["delivered_at"])
                self.assertIsNotNone(row["next_attempt_at"])
                self.assertIsNotNone(
                    db.execute(
                        "SELECT to_regclass('ecology_proposals_completed') AS present"
                    ).fetchone()["present"]
                )
                self.assertEqual(
                    db.execute(
                        "SELECT checksum FROM schema_migrations WHERE version=104"
                    ).fetchone()["checksum"],
                    expected,
                )
                self.assertEqual(migrate(db, migrations), 0)
                db.execute(f"DROP SCHEMA {schema} CASCADE")
