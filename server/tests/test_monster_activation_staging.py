"""Regression coverage for read-only and guarded NPC catalog staging."""
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import stage_monster_spell_activation as staging


class FakeConnection:
    def __init__(self, revision="base", baseline=None):
        self.revision = revision
        self.baseline = baseline or [("class-catalog.json", "c" * 64)]
        self.sql = []
        self.current = ""

    def transaction(self):
        return nullcontext()

    def execute(self, sql, parameters=None):
        self.sql.append((sql, parameters))
        self.current = sql
        return self

    def fetchone(self):
        if "native_catalog_active" in self.current:
            return (self.revision,)
        return None

    def fetchall(self):
        return self.baseline

    @property
    def writes(self):
        return [sql for sql, _ in self.sql if "INSERT" in sql or "UPDATE" in sql]


class MonsterActivationStagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.payloads = {
            "native-npc-spell-effect-trees.json": b'{"trees": []}\n',
            "native-class-casting-roots.json": b'{"roots": []}\n',
        }
        self.manifest = {
            "schema": "native-npc-activation-candidate-v1",
            "activated": False,
            "base_revision": "base",
            "changed_documents": {
                name: hashlib.sha256(raw).hexdigest()
                for name, raw in self.payloads.items()
            },
            "unchanged_documents": {"class-catalog.json": "c" * 64},
            "execution_validated": True,
            "class_regressions_passed": True,
        }
        receipt = b'{"validated": true}\n'
        self.receipt_hash = hashlib.sha256(receipt).hexdigest()
        helper = Path(__file__).parents[2] / "AGENTS.md"
        self.helper_name = "AGENTS.md"
        self.manifest["execution_validation_sha256"] = self.receipt_hash
        self.manifest["tested_runtime_code_sha256"] = {
            self.helper_name: hashlib.sha256(helper.read_bytes()).hexdigest()
        }
        self.write_package()
        (self.directory / "execution-validation.json").write_bytes(receipt)

    def write_package(self):
        for name, raw in self.payloads.items():
            (self.directory / name).write_bytes(raw)
        (self.directory / "manifest.json").write_text(json.dumps(self.manifest))

    def add_cost_document(self):
        name = staging.COST_PATH
        raw = b'{"schema": "native-spell-resource-costs-v1", "spells": {}}\n'
        self.payloads[name] = raw
        self.manifest["changed_documents"][name] = hashlib.sha256(raw).hexdigest()
        self.write_package()

    def no_write_calls(self, connection):
        self.assertEqual(connection.writes, [])

    def test_dry_run_is_read_only_and_does_not_write_catalog_rows(self):
        connection = FakeConnection()
        with patch.object(
            staging,
            "stage_release",
            return_value={
                "dry_run": True,
                "staged": False,
                "resource_cost_documents": 2,
            },
        ) as generic_stage:
            result = staging.stage(connection, self.directory)
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["staged"])
        self.assertEqual(result["npc_documents"], 2)
        self.assertEqual(connection.sql[0][0], "SET TRANSACTION READ ONLY")
        self.no_write_calls(connection)
        generic_stage.assert_called_once()

    def test_unrelated_class_document_is_still_rejected(self):
        self.manifest["changed_documents"]["native-class-catalog.json"] = "d" * 64
        self.write_package()
        with self.assertRaisesRegex(ValueError, "cannot replace class"):
            staging.documents(self.directory)

    def test_changed_source_hash_is_rejected(self):
        (self.directory / "native-npc-spell-effect-trees.json").write_bytes(
            b'{"trees": ["changed"]}\n'
        )
        with self.assertRaisesRegex(ValueError, "changed after validation"):
            staging.documents(self.directory)

    def test_malformed_package_is_rejected(self):
        self.manifest["activated"] = True
        self.write_package()
        with self.assertRaisesRegex(ValueError, "Invalid inactive"):
            staging.documents(self.directory)

    def test_active_revision_drift_fails_before_generic_staging_or_writes(self):
        connection = FakeConnection(revision="new-active")
        with patch.object(staging, "stage_release") as generic_stage:
            with self.assertRaisesRegex(ValueError, "Active catalog changed"):
                staging.stage(connection, self.directory, dry_run=False)
        generic_stage.assert_not_called()
        self.no_write_calls(connection)

    def test_unchanged_class_manifest_drift_fails_before_writes(self):
        connection = FakeConnection(baseline=[("class-catalog.json", "x" * 64)])
        with patch.object(staging, "stage_release") as generic_stage:
            with self.assertRaisesRegex(ValueError, "preservation manifest differs"):
                staging.stage(connection, self.directory, dry_run=False)
        generic_stage.assert_not_called()
        self.no_write_calls(connection)

    def test_optional_cost_document_is_allowed_when_missing_from_base(self):
        self.add_cost_document()
        connection = FakeConnection()

        def generic_stage(
            conn,
            directory,
            expected_revision,
            *,
            base_revision=None,
            dry_run,
            document_provider
        ):
            exported = document_provider(directory)
            return {
                "expected_active_revision": expected_revision,
                "base_revision": expected_revision
                if base_revision is None
                else base_revision,
                "resource_cost_documents": len(exported),
                "changed_documents": [entry["path"] for entry in exported],
                "dry_run": dry_run,
                "staged": True,
                "activated": False,
            }

        with patch.object(staging, "stage_release", side_effect=generic_stage):
            result = staging.stage(connection, self.directory, dry_run=False)

        self.assertEqual(result["npc_documents"], 3)
        self.assertEqual(
            set(result["changed_documents"]), set(staging.PATHS) | {staging.COST_PATH}
        )
        self.assertEqual(result["base_revision"], "base")

    def test_optional_cost_document_cannot_replace_costs_already_in_base(self):
        self.add_cost_document()
        connection = FakeConnection(
            baseline=[("class-catalog.json", "c" * 64), (staging.COST_PATH, "z" * 64)]
        )
        with patch.object(staging, "stage_release") as generic_stage:
            with self.assertRaisesRegex(ValueError, "cannot replace an existing"):
                staging.stage(connection, self.directory, dry_run=False)
        generic_stage.assert_not_called()
        self.no_write_calls(connection)

    def test_staging_requires_matching_execution_receipt(self):
        (self.directory / "execution-validation.json").unlink()
        connection = FakeConnection()
        with patch.object(staging, "stage_release") as generic_stage:
            with self.assertRaisesRegex(ValueError, "matching execution receipt"):
                staging.stage(connection, self.directory, dry_run=False)
        generic_stage.assert_not_called()
        self.no_write_calls(connection)

    def test_staging_rejects_tampered_receipt_and_changed_runtime_source(self):
        receipt = self.directory / "execution-validation.json"
        receipt.write_bytes(b'{"validated": false}\n')
        connection = FakeConnection()
        with patch.object(staging, "stage_release") as generic_stage:
            with self.assertRaisesRegex(ValueError, "matching execution receipt"):
                staging.stage(connection, self.directory, dry_run=False)
        generic_stage.assert_not_called()
        self.no_write_calls(connection)

        receipt.write_bytes(b'{"validated": true}\n')
        self.manifest["tested_runtime_code_sha256"][self.helper_name] = "0" * 64
        self.write_package()
        connection = FakeConnection()
        with patch.object(staging, "stage_release") as generic_stage:
            with self.assertRaisesRegex(ValueError, "Tested runtime sources changed"):
                staging.stage(connection, self.directory, dry_run=False)
        generic_stage.assert_not_called()
        self.no_write_calls(connection)

    def test_staging_requires_execution_and_class_regression_flags(self):
        for field in ("execution_validated", "class_regressions_passed"):
            with self.subTest(field=field):
                self.manifest[field] = False
                self.write_package()
                connection = FakeConnection()
                with patch.object(staging, "stage_release") as generic_stage:
                    with self.assertRaisesRegex(ValueError, "requires execution"):
                        staging.stage(connection, self.directory, dry_run=False)
                generic_stage.assert_not_called()
                self.no_write_calls(connection)
                self.manifest[field] = True

    def test_injected_generic_stage_keeps_base_and_reports_npc_document_count(self):
        connection = FakeConnection()

        def generic_stage(
            conn,
            directory,
            expected_revision,
            *,
            base_revision=None,
            dry_run,
            document_provider
        ):
            self.assertIs(conn, connection)
            self.assertEqual(expected_revision, "base")
            self.assertIsNone(base_revision)
            resolved_base = (
                expected_revision if base_revision is None else base_revision
            )
            exported = document_provider(directory)
            return {
                "expected_active_revision": expected_revision,
                "base_revision": resolved_base,
                "resource_cost_documents": len(exported),
                "changed_documents": [entry["path"] for entry in exported],
                "dry_run": dry_run,
                "staged": True,
                "activated": False,
            }

        with patch.object(
            staging, "stage_release", side_effect=generic_stage
        ) as injected:
            result = staging.stage(connection, self.directory, dry_run=False)

        injected.assert_called_once()
        self.assertEqual(result["expected_active_revision"], "base")
        self.assertEqual(result["base_revision"], "base")
        self.assertEqual(result["npc_documents"], len(staging.PATHS))
        self.assertEqual(set(result["changed_documents"]), set(staging.PATHS))
        self.assertTrue(result["staged"])
        self.assertFalse(result["activated"])


if __name__ == "__main__":
    unittest.main()
