"""Fresh-volume restore rejects incomplete seeds and propagates restore errors."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "database/docker/20-restore-runtime.sh"


class CleanBackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bootstrap = self.root / "seed"
        self.bootstrap.mkdir()
        self.commands = self.root / "commands"
        self.commands.mkdir()
        self.log = self.root / "calls.jsonl"
        mock = (
            f"#!{sys.executable}\n"
            + r"""
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
text = sys.stdin.read() if name == "psql" else ""
with open(os.environ["MOCK_LOG"], "a") as output:
    output.write(json.dumps(dict(command=name, args=sys.argv[1:], stdin=text)) + "\n")
if name == "pg_restore":
    failure = "MOCK_LIST_FAIL" if "--list" in sys.argv else "MOCK_RESTORE_FAIL"
else:
    failure = "MOCK_MANIFEST_FAIL" if "clean_seed_manifest_valid" in text else "MOCK_AUDIT_FAIL"
raise SystemExit(1 if os.environ.get(failure) else 0)
"""
        )
        for name in ("pg_restore", "psql"):
            path = self.commands / name
            path.write_text(mock)
            path.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": str(self.commands) + os.pathsep + os.environ["PATH"],
            "WAKEMU_BOOTSTRAP_DIR": str(self.bootstrap),
            "POSTGRES_USER": "fixture_user",
            "POSTGRES_DB": "fixture_database",
            "MOCK_LOG": str(self.log),
        }
        self.seed()

    def seed(self, body=b"PGDMP-fixture"):
        (self.bootstrap / "wakemu-clean.dump").write_bytes(body)
        (self.bootstrap / "wakemu-clean.dump.sha256").write_text(
            hashlib.sha256(body).hexdigest() + "  wakemu-clean.dump\n"
        )
        (self.bootstrap / "wakemu-clean.dump.manifest.json").write_text(
            json.dumps({"format": "wakemu-clean-database-v1"})
        )

    def run_restore(self, **extra):
        return subprocess.run(
            ["sh", str(SCRIPT)],
            env={**self.env, **extra},
            text=True,
            capture_output=True,
        )

    def calls(self):
        return (
            [json.loads(line) for line in self.log.read_text().splitlines()]
            if self.log.exists()
            else []
        )

    def test_missing_and_corrupted_artifacts_never_reach_postgres(self):
        for filename in (
            "wakemu-clean.dump",
            "wakemu-clean.dump.sha256",
            "wakemu-clean.dump.manifest.json",
        ):
            with self.subTest(missing=filename):
                self.seed()
                (self.bootstrap / filename).unlink()
                result = self.run_restore()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Clean database seed missing", result.stderr)
                self.assertEqual(self.calls(), [])
        self.seed()
        (self.bootstrap / "wakemu-clean.dump").write_bytes(b"PGDMP-corrupted")
        result = self.run_restore()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_lfs_pointer_is_not_treated_as_a_database_archive(self):
        self.seed(b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\n")
        result = self.run_restore()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("git lfs pull", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_invalid_archive_list_never_modifies_database(self):
        result = self.run_restore(MOCK_LIST_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid clean database archive", result.stderr)
        self.assertEqual([row["command"] for row in self.calls()], ["pg_restore"])
        self.assertIn("--list", self.calls()[0]["args"])

    def test_manifest_failure_stops_before_archive_restore(self):
        result = self.run_restore(MOCK_MANIFEST_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            [row["command"] for row in self.calls()], ["pg_restore", "psql"]
        )

    def test_restore_and_final_audit_failures_do_not_report_success(self):
        for failure, expected_calls in (
            ("MOCK_RESTORE_FAIL", 3),
            ("MOCK_AUDIT_FAIL", 4),
        ):
            with self.subTest(failure=failure):
                self.log.unlink(missing_ok=True)
                result = self.run_restore(**{failure: "1"})
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Wakemu clean seed restored", result.stdout)
                self.assertEqual(len(self.calls()), expected_calls)

    def test_complete_archive_restores_atomically_with_no_owner_or_acl_changes(self):
        result = self.run_restore()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(
            [row["command"] for row in calls],
            ["pg_restore", "psql", "pg_restore", "psql"],
        )
        restore = calls[2]["args"]
        for flag in (
            "--no-owner",
            "--no-acl",
            "--exit-on-error",
            "--single-transaction",
        ):
            self.assertIn(flag, restore)
        self.assertEqual(restore[restore.index("--username") + 1], "fixture_user")
        self.assertEqual(restore[restore.index("--dbname") + 1], "fixture_database")
        self.assertNotIn("--clean", restore)
        self.assertIn("admin/admin", result.stdout)


if __name__ == "__main__":
    unittest.main()
