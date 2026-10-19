import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wakfu_server.dungeon_runtime_config import canonical_hash
from tools import apply_dungeon_role_repairs as apply_tool


class FakeDatabase:
    def __init__(
        self,
        *,
        version=1,
        source=None,
        context_version=1,
        catalog_revision=9,
        catalog_sha=None,
    ):
        self.version = version
        self.source = source
        self.context_version = context_version
        self.catalog_revision = catalog_revision
        self.catalog_sha = catalog_sha
        self.sql = []

    def execute(self, statement, params=None):
        self.sql.append((statement, params))
        if "native_catalog_active" in statement:
            if self.catalog_sha is None:
                return FakeCursor(None)
            return FakeCursor(
                dict(revision=self.catalog_revision, sha256=self.catalog_sha)
            )
        if "pg_advisory_xact_lock" in statement:
            return FakeCursor(None)
        if "dungeon_runtime_active_configurations" in statement:
            return FakeCursor(
                dict(policy_version=self.version, configuration=self.source)
            )
        if "dungeon_context_active_policies" in statement:
            return FakeCursor(dict(policy_version=self.context_version))
        raise AssertionError(f"Unexpected SQL: {statement}")


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class ApplyGeneratedDungeonRolesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.native_path = self.root / "native.json"
        self.native_raw = b'{"monsters":[]}'
        self.native_path.write_bytes(self.native_raw)
        self.source = {
            "version": 1,
            "route": {"key": "route:test"},
            "topology": {"entry": 10, "rooms": [10, 11]},
            "context_policy": {"policy_version": 1, "entry": 10},
            "level_policy": {"min": 1, "max": 10},
            "compiled_plan": {
                "rooms": [
                    {"order": 1, "monsters": [{"ref_id": 4, "count": 2}]},
                    {"order": 2, "monsters": [{"ref_id": 9, "count": 1}]},
                ]
            },
        }
        self.candidate = json.loads(json.dumps(self.source))
        self.candidate["version"] = 2
        self.candidate["compiled_plan"]["rooms"][0]["monsters"][0]["ref_id"] = 5
        self.row = dict(
            route_key="route:test",
            source_version=1,
            source_sha256=canonical_hash(self.source),
            candidate_version=2,
            candidate_sha256=canonical_hash(self.candidate),
            path="unused.json",
        )
        self.manifest = dict(
            native_monsters_path=str(self.native_path),
            native_monsters_sha256=hashlib.sha256(self.native_raw).hexdigest(),
            catalog_revision=9,
        )
        self.candidates = [(self.row, self.candidate)]

    def database(self, **kwargs):
        values = dict(
            source=self.source,
            catalog_sha=self.manifest["native_monsters_sha256"],
        )
        values.update(kwargs)
        return FakeDatabase(
            **values,
        )

    def patch_qualified_candidate(self):
        return patch(
            "prepare_generated_dungeon_role_repair.prepare",
            return_value=(self.candidate, {"installed": False}),
        )

    def test_read_only_qualification_does_not_issue_mutations(self):
        db = self.database()
        with self.patch_qualified_candidate():
            result = apply_tool.apply(db, self.manifest, self.candidates)
        self.assertEqual(
            result,
            dict(
                qualified=True,
                installed=False,
                candidates=1,
                future_runs_only=True,
            ),
        )
        self.assertFalse(
            any(
                "FOR UPDATE" in sql or "pg_advisory_xact_lock" in sql
                for sql, _ in db.sql
            )
        )

    def test_install_backs_up_exact_source_before_installing_candidate(self):
        db = self.database()
        backup = self.root / "backup.json"
        observed = []

        def install(_db, candidate):
            observed.append(
                (backup.exists(), json.loads(backup.read_text()), candidate)
            )

        with self.patch_qualified_candidate(), patch.object(
            apply_tool, "install_configuration", install
        ):
            result = apply_tool.apply(
                db, self.manifest, self.candidates, install=True, backup=backup
            )
        self.assertTrue(result["installed"])
        self.assertEqual(len(result["policies"]), 1)
        self.assertEqual(
            result["backup_sha256"], hashlib.sha256(backup.read_bytes()).hexdigest()
        )
        self.assertEqual(len(observed), 1)
        existed, saved, installed_candidate = observed[0]
        self.assertTrue(existed)
        self.assertEqual(saved["originals"][0]["configuration"], self.source)
        self.assertEqual(installed_candidate, self.candidate)

    def test_stale_context_source_and_catalog_fail_before_any_install(self):
        backup = self.root / "backup.json"
        for db in (
            self.database(context_version=7),
            self.database(version=7),
            self.database(catalog_sha="0" * 64),
        ):
            with self.subTest(db=db), self.patch_qualified_candidate(), patch.object(
                apply_tool, "install_configuration"
            ) as install:
                with self.assertRaises(ValueError):
                    apply_tool.apply(
                        db, self.manifest, self.candidates, install=True, backup=backup
                    )
                install.assert_not_called()
                self.assertFalse(backup.exists())

    def test_failed_candidate_reconstruction_does_not_write_backup_or_install(self):
        db = self.database()
        backup = self.root / "backup.json"
        with patch(
            "prepare_generated_dungeon_role_repair.prepare",
            return_value=(self.source, {}),
        ), patch.object(apply_tool, "install_configuration") as install:
            with self.assertRaisesRegex(ValueError, "qualified role-only repair"):
                apply_tool.apply(
                    db, self.manifest, self.candidates, install=True, backup=backup
                )
        install.assert_not_called()
        self.assertFalse(backup.exists())


if __name__ == "__main__":
    unittest.main()
