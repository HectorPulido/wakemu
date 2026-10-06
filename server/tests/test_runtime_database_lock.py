import os
from postgres_case import PostgresCase
from wakfu_server.postgres import Database


class RuntimeDatabaseLockTests(PostgresCase):
    def test_same_database_lock_excludes_second_world_until_owner_closes(self):
        password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        first = Database(self.database_url, password_file=password_file)
        second = Database(self.database_url, password_file=password_file)
        self.addCleanup(first.close)
        self.addCleanup(second.close)

        first.acquire_runtime_lock()
        with self.assertRaisesRegex(RuntimeError, "Another world owns"):
            second.acquire_runtime_lock()

        first.close()
        second.acquire_runtime_lock()
        self.assertIsNotNone(second.runtime_lock_connection)
