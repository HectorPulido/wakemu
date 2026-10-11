"""Execute generated dungeon migrations against isolated normalized storage."""
import copy
from pathlib import Path
import sys

import psycopg
from postgres_case import PostgresCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_physical_dungeon_configuration import migration


class GeneratedDungeonConfigurationPostgresTests(PostgresCase):
    def configuration(self, version):
        return dict(
            route=dict(key="generated-storage-test", template_id=91, definition_id=90),
            version=version,
            provenance="Isolated SQL generator acceptance",
            marker=version,
        )

    def test_replay_preserves_versions_and_moves_relational_active_pointer(self):
        one, two = self.configuration(1), self.configuration(2)
        with self.store.connection() as db:
            db.execute(migration(one))
            db.execute(migration(one))
            db.execute(migration(two))
            versions = db.execute(
                "SELECT policy_version,configuration FROM dungeon_runtime_configurations WHERE route_key=%s ORDER BY policy_version",
                (one["route"]["key"],),
            ).fetchall()
            self.assertEqual(
                [(row["policy_version"], row["configuration"]) for row in versions],
                [(1, one), (2, two)],
            )
            self.assertEqual(
                db.execute(
                    "SELECT policy_version FROM dungeon_runtime_active_configurations WHERE route_key=%s",
                    (one["route"]["key"],),
                ).fetchone()["policy_version"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT policy_version FROM dungeon_context_active_policies WHERE route_key=%s",
                    (one["route"]["key"],),
                ).fetchone()["policy_version"],
                2,
            )
            self.assertFalse(
                db.execute(
                    "SELECT name FROM settings WHERE name LIKE %s",
                    ("dungeon_runtime_%:generated-storage-test%",),
                ).fetchall()
            )

    def test_conflicting_version_rolls_back_without_moving_pointer(self):
        original = self.configuration(1)
        with self.store.connection() as db:
            db.execute(migration(original))
        conflict = copy.deepcopy(original)
        conflict["marker"] = "conflicting-value"
        with self.assertRaises(psycopg.Error):
            with self.store.connection() as db:
                db.execute(migration(conflict))
        with self.store.connection() as db:
            row = db.execute(
                "SELECT configuration FROM dungeon_runtime_configurations WHERE route_key=%s AND policy_version=1",
                (original["route"]["key"],),
            ).fetchone()
            self.assertEqual(row["configuration"], original)
            self.assertEqual(
                db.execute(
                    "SELECT policy_version FROM dungeon_runtime_active_configurations WHERE route_key=%s",
                    (original["route"]["key"],),
                ).fetchone()["policy_version"],
                1,
            )
