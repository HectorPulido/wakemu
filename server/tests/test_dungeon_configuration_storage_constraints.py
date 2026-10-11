"""Database invariants and lossless failure paths for dedicated dungeon storage."""
import json
from pathlib import Path

import psycopg

from postgres_case import PostgresCase


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations/114_dungeon_runtime_configuration_tables.sql"
).read_text()


class DungeonConfigurationStorageConstraintsTests(PostgresCase):
    def seed(self):
        config = {"route": {"key": "storage_constraints"}, "version": 1}
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO dungeon_runtime_configurations(route_key,policy_version,configuration) "
                "VALUES(%s,1,%s::jsonb)",
                ("storage_constraints", json.dumps(config)),
            )
            db.execute(
                "INSERT INTO dungeon_runtime_active_configurations VALUES(%s,1)",
                ("storage_constraints",),
            )
        return config

    def test_database_rejects_mutation_deletion_missing_version_and_wrong_identity(
        self,
    ):
        self.seed()
        for statement in (
            "UPDATE dungeon_runtime_configurations SET configuration=configuration || "
            "'{\"notes\":\"changed\"}'::jsonb WHERE route_key='storage_constraints'",
            "DELETE FROM dungeon_runtime_configurations WHERE route_key='storage_constraints'",
        ):
            with self.subTest(statement=statement), self.assertRaisesRegex(
                psycopg.errors.RaiseException, "immutable"
            ):
                with self.store.connection() as db:
                    db.execute(statement)
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE dungeon_runtime_active_configurations SET policy_version=2 "
                    "WHERE route_key='storage_constraints'"
                )
        with self.assertRaises(psycopg.errors.CheckViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO dungeon_runtime_configurations VALUES(%s,1,%s::jsonb,DEFAULT)",
                    (
                        "wrong_identity",
                        json.dumps({"route": {"key": "other"}, "version": 1}),
                    ),
                )

    def test_migration_preserves_unrelated_settings_with_similar_names(self):
        names = ("dungeonXruntimeYconfig:keep", "dungeonXruntimeYactive:keep")
        with self.store.connection() as db:
            for name in names:
                db.execute(
                    "INSERT INTO settings(name,value) VALUES(%s,'{}'::jsonb)", (name,)
                )
            db.execute(MIGRATION)
            for name in names:
                self.assertIsNotNone(
                    db.execute(
                        "SELECT value FROM settings WHERE name=%s", (name,)
                    ).fetchone()
                )

    def test_orphan_pointer_and_conflicting_version_leave_source_rows_intact(self):
        config = self.seed()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES(%s,%s::jsonb)",
                ("dungeon_runtime_active:missing_route", json.dumps({"version": 2})),
            )
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.store.connection() as db:
                db.execute(MIGRATION)
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT value FROM settings WHERE name='dungeon_runtime_active:missing_route'"
                ).fetchone()
            )
            db.execute(
                "DELETE FROM settings WHERE name='dungeon_runtime_active:missing_route'"
            )
            db.execute(
                "INSERT INTO settings(name,value) VALUES(%s,%s::jsonb)",
                (
                    "dungeon_runtime_config:storage_constraints:v1",
                    json.dumps(dict(config, notes="conflict")),
                ),
            )
        with self.assertRaisesRegex(psycopg.errors.RaiseException, "conflicts"):
            with self.store.connection() as db:
                db.execute(MIGRATION)
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT value FROM settings WHERE name='dungeon_runtime_config:storage_constraints:v1'"
                ).fetchone()
            )
            self.assertEqual(
                config,
                db.execute(
                    "SELECT configuration FROM dungeon_runtime_configurations "
                    "WHERE route_key='storage_constraints' AND policy_version=1"
                ).fetchone()["configuration"],
            )
