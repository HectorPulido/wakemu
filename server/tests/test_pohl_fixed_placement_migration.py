"""Focused352 SQL upgrade; isolated schema with exact reviewed versions only."""
import gzip
import json
import os
from pathlib import Path
import unittest
import uuid

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from postgres_case import isolated_test_url

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures/pohl-fixed-placement"


class PohlPlacementMigrationTests(unittest.TestCase):
    def test_upgrade_preserves_existing_pin_and_replays_without_changes(self):
        if not os.environ.get("WAKFU_POSTGRES_TEST_URL"):
            self.skipTest("Explicit isolated PostgreSQL database required")
        url = isolated_test_url()
        password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        kwargs = (
            {}
            if password_file is None
            else dict(password=Path(password_file).read_text().strip())
        )
        admin = psycopg.connect(url, autocommit=True, **kwargs)
        self.addCleanup(admin.close)
        schema = "pohl352_" + uuid.uuid4().hex
        admin.execute("CREATE SCHEMA " + schema)
        self.addCleanup(lambda: admin.execute("DROP SCHEMA " + schema + " CASCADE"))
        db = psycopg.connect(
            make_conninfo(url, options="-c search_path=" + schema),
            autocommit=True,
            row_factory=dict_row,
            **kwargs,
        )
        self.addCleanup(db.close)
        with db.transaction():
            db.execute(
                "CREATE TABLE settings(name text PRIMARY KEY,value jsonb NOT NULL)"
            )
            db.execute("CREATE TABLE dungeon_instances(instance_id bigint PRIMARY KEY)")
            for name in (
                "070_dungeon_context_policy_versions.sql",
                "114_dungeon_runtime_configuration_tables.sql",
            ):
                db.execute((ROOT / "migrations" / name).read_text())
        migration = (
            ROOT / "migrations/352_pohl_reviewed_fixed_initial_placement.sql"
        ).read_text()
        db.execute(migration)
        self.assertEqual(
            db.execute(
                "SELECT count(*) AS n FROM dungeon_runtime_configurations"
            ).fetchone()["n"],
            0,
        )
        old, new = [
            json.loads(
                gzip.decompress(
                    (FIXTURES / f"configuration184v{v}.json.gz").read_bytes()
                )
            )
            for v in (6, 7)
        ]
        context = old["context_policy"]
        with db.transaction():
            db.execute(
                "INSERT INTO dungeon_runtime_configurations(route_key,policy_version,configuration) VALUES(%s,6,%s)",
                ("native_dungeon_184", Jsonb(old)),
            )
            fields = ",".join(context)
            db.execute(
                f"INSERT INTO dungeon_context_policy_versions({fields}) SELECT {fields} FROM jsonb_populate_record(NULL::dungeon_context_policy_versions,%s)",
                (Jsonb(context),),
            )
            db.execute(
                "INSERT INTO dungeon_runtime_active_configurations VALUES('native_dungeon_184',6)"
            )
            db.execute(
                "INSERT INTO dungeon_context_active_policies VALUES('native_dungeon_184',6)"
            )
            db.execute(
                "INSERT INTO dungeon_instances VALUES(370,'native_dungeon_184',6)"
            )
        old_context = db.execute(
            "SELECT * FROM dungeon_context_policy_versions"
        ).fetchone()
        old_pin = db.execute("SELECT * FROM dungeon_instances").fetchone()
        db.execute(migration)
        self.assertEqual(
            db.execute(
                "SELECT configuration FROM dungeon_runtime_configurations WHERE policy_version=6"
            ).fetchone()["configuration"],
            old,
        )
        self.assertEqual(
            db.execute(
                "SELECT * FROM dungeon_context_policy_versions WHERE policy_version=6"
            ).fetchone(),
            old_context,
        )
        self.assertEqual(
            db.execute("SELECT * FROM dungeon_instances").fetchone(), old_pin
        )
        self.assertEqual(
            db.execute(
                "SELECT configuration FROM dungeon_runtime_configurations WHERE policy_version=7"
            ).fetchone()["configuration"],
            new,
        )
        for table in (
            "dungeon_runtime_active_configurations",
            "dungeon_context_active_policies",
        ):
            self.assertEqual(
                db.execute("SELECT policy_version FROM " + table).fetchone()[
                    "policy_version"
                ],
                7,
            )
        tables = (
            "dungeon_runtime_configurations",
            "dungeon_context_policy_versions",
            "dungeon_runtime_active_configurations",
            "dungeon_context_active_policies",
            "dungeon_instances",
        )
        before = {
            table: db.execute("SELECT * FROM " + table).fetchall() for table in tables
        }
        db.execute(migration)
        self.assertEqual(
            {
                table: db.execute("SELECT * FROM " + table).fetchall()
                for table in tables
            },
            before,
        )


if __name__ == "__main__":
    unittest.main()
