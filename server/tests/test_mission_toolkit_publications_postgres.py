"""Real SQL publications isolated in a rolled-back schema; no player fixtures."""

import json
import os
from pathlib import Path
import unittest
from uuid import uuid4

from psycopg import sql

from wakfu_server.achievements import mission_toolkit as toolkit
from wakfu_server.store import Store


@unittest.skipUnless(os.environ.get("WAKFU_DATABASE_URL"), "Local PostgreSQL required")
class MissionToolkitPublicationTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(
            os.environ["WAKFU_DATABASE_URL"],
            password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
        )
        self.context = self.store.connection()
        self.db = self.context.__enter__()
        self.schema = "test_mission_toolkit_" + uuid4().hex
        self.db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.db.execute(
            sql.SQL("SET LOCAL search_path TO {},public").format(
                sql.Identifier(self.schema)
            )
        )
        source = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "372_mission_toolkit_profiles.sql"
        )
        self.db.execute(source.read_text(), prepare=False)
        toolkit._CACHE.clear()

    def tearDown(self):
        self.context.__exit__(
            RuntimeError, RuntimeError("rollback-only publication fixture"), None
        )
        self.store.close()
        toolkit._CACHE.clear()

    def test_publish_activate_reuse_and_immutable_version(self):
        first = toolkit.install_rii(self.db, activate=True)
        self.assertEqual(
            (first["id"], first["version"], first["active"]), ("rii", 1, True)
        )
        self.assertEqual(toolkit.install_rii(self.db), first)
        body = toolkit.get_profile(self.db, "rii")
        self.assertEqual(body, json.loads(toolkit.RII_PROFILE.read_text()))
        with self.assertRaises(Exception):
            with self.db.transaction():
                self.db.execute(
                    "UPDATE mission_toolkit_profiles SET document='{}' WHERE profile_id='rii'"
                )
        revised = dict(
            body,
            evidence=body["evidence"]
            + ["Reviewed publication revision for SQL acceptance."],
        )
        second = toolkit.install(self.db, revised)
        self.assertEqual((second["version"], second["active"]), (2, False))
        toolkit.activate(self.db, "rii", 2)
        self.assertEqual(toolkit.get_profile(self.db, "rii"), revised)
        self.assertEqual(
            [row["active"] for row in toolkit.installed(self.db)], [False, True]
        )

    def test_active_overlap_rejected_and_event_projection_is_targeted(self):
        toolkit.install_rii(self.db, activate=True)
        duplicate = dict(
            json.loads(toolkit.RII_PROFILE.read_text()), id="overlapping-test-profile"
        )
        with self.assertRaisesRegex(ValueError, "overlapping"):
            toolkit.install(self.db, duplicate, activate=True)
        row = self.db.execute(
            "SELECT * FROM mission_toolkit_profiles WHERE profile_id='rii'"
        ).fetchone()
        compiled = toolkit._load(self.db, row)
        profile, native = toolkit._project(
            compiled,
            dict(kind="resource_harvest", reference=31007, quantity=1),
            dict(id=1, map_id=1385),
        )
        self.assertEqual([row["id"] for row in profile["bindings"]], ["flower-seed"])
        self.assertEqual(set(native), {5143, 5145, 5146, 5155, 5156, 5160})
        completion, _ = toolkit._project(
            compiled,
            dict(kind="quest_completed", reference=5143, quantity=1),
            dict(id=1, map_id=1385),
        )
        self.assertFalse(completion["bindings"])
        self.assertTrue(
            any(row["child_quest_id"] == 5143 for row in completion["links"])
        )
        self.assertIsNone(
            toolkit._project(
                compiled,
                dict(kind="resource_harvest", reference=31007, quantity=1),
                dict(id=1, map_id=527),
            )
        )
