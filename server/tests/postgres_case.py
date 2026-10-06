"""Isolated schemas for server integration tests; never touches public tables."""
import os
from pathlib import Path
import unittest
import uuid


class PostgresCase(unittest.TestCase):
    def setUp(self):
        url = os.environ.get("WAKFU_POSTGRES_TEST_URL")
        if not url:
            self.skipTest("Isolated PostgreSQL required")
        from psycopg.conninfo import make_conninfo
        from wakfu_server.postgres import Database, migrate
        from wakfu_server.store import Store

        password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        admin = Database(url, password_file=password_file)
        self.addCleanup(admin.close)
        schema = "case_" + uuid.uuid4().hex
        with admin.connection() as db:
            db.execute(f"CREATE SCHEMA {schema}")
            db.execute(f"SET LOCAL search_path TO {schema}")
            migrate(
                db,
                Path(
                    os.environ.get(
                        "WAKFU_MIGRATIONS_TEST_DIR",
                        Path(__file__).resolve().parents[1] / "migrations",
                    )
                ),
            )

        def cleanup_schema():
            with admin.connection() as db:
                db.execute(f"DROP SCHEMA {schema} CASCADE")

        self.addCleanup(cleanup_schema)
        self.database_url = make_conninfo(url, options=f"-c search_path={schema}")
        self.store = Store(self.database_url, password_file=password_file)
        self.addCleanup(self.store.close)

    def reopen(self):
        from wakfu_server.store import Store

        store = Store(
            self.database_url,
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        self.addCleanup(store.close)
        return store
