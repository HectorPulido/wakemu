"""Isolated schemas for server integration tests; never touches public tables."""
import os
from pathlib import Path
import unittest
import uuid

from psycopg.conninfo import conninfo_to_dict


def isolated_test_url():
    """Require an explicit non-runtime DSN before any test migration runs."""
    url = os.environ.get("WAKFU_POSTGRES_TEST_URL")
    if not url:
        raise RuntimeError("Set WAKFU_POSTGRES_TEST_URL to an isolated test database")
    database = conninfo_to_dict(url).get("dbname")
    if not database or database in {"wakemu", "wakemu_runtime"}:
        raise RuntimeError(
            "Refusing to run PostgreSQL tests against a runtime database"
        )
    return url


class PostgresCase(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("WAKFU_POSTGRES_TEST_URL"):
            self.skipTest("Isolated PostgreSQL required")
        url = isolated_test_url()
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
