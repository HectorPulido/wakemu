"""Dungeon tools read and emit normalized version storage without settings keys."""
from contextlib import contextmanager
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_classic_dungeon_hybrid_structure import active_configurations
from build_physical_dungeon_configuration import migration


class DungeonConfigurationToolStorageTests(unittest.TestCase):
    def test_read_only_audit_resolves_active_version_in_one_join(self):
        configuration = dict(route=dict(key="native_dungeon_68"), version=17)
        db = Mock()
        db.execute.return_value.fetchall.return_value = [
            ("native_dungeon_68", 17, configuration)
        ]

        @contextmanager
        def connection(*args, **kwargs):
            yield db

        with tempfile.TemporaryDirectory() as directory:
            password = Path(directory) / "password"
            password.write_text("test-password")
            with patch.dict(
                os.environ,
                WAKFU_DATABASE_PASSWORD_FILE=str(password),
                WAKFU_DATABASE_URL="dbname=isolated",
            ), patch("psycopg.connect", side_effect=connection):
                result = active_configurations()
        self.assertEqual(
            result,
            {
                "native_dungeon_68": (
                    configuration,
                    "postgres.dungeon_runtime_configurations:native_dungeon_68:v17",
                )
            },
        )
        queries = [call.args[0] for call in db.execute.call_args_list]
        self.assertEqual(queries[0], "SET TRANSACTION READ ONLY")
        self.assertEqual(len(queries), 2)
        self.assertIn("versions.policy_version=active.policy_version", queries[1])
        self.assertNotIn("settings", queries[1])

    def test_generated_migration_uses_versioned_relational_storage(self):
        sql = migration(dict(route=dict(key="native_dungeon_68"), version=17))
        self.assertIn(
            "INSERT INTO dungeon_runtime_configurations(route_key,policy_version,configuration)",
            sql,
        )
        self.assertIn(
            "INSERT INTO dungeon_runtime_active_configurations(route_key,policy_version)",
            sql,
        )
        self.assertIn("configuration<>config", sql)
        self.assertNotIn("settings", sql)
        self.assertNotIn("dungeon_runtime_config:", sql)
