"""Regression coverage for bounded, sanitized combat baseline provenance."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


_SPEC = importlib.util.spec_from_file_location(
    "combat_baseline_inventory",
    Path(__file__).resolve().parents[1] / "tools/combat_baseline_inventory.py",
)
inventory = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(inventory)


class CombatBaselineInventoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf8")
        return path

    def test_source_identity_changes_for_implementation_and_not_runtime_data(self):
        path = self.write(
            "server/wakfu_server/combat/damage.py", "def damage():\n    return 1\n"
        )
        self.write("server/requirements.txt", "psycopg==3.2.0\n")
        first = inventory.source_manifest(self.root)
        self.write(".runtime/private.json", '{"token":"not-source"}')
        second = inventory.source_manifest(self.root)
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(first["file_count"], 2)
        path.write_text("def damage():\n    return 2\n", encoding="utf8")
        third = inventory.source_manifest(self.root)
        self.assertNotEqual(first["sha256"], third["sha256"])
        self.assertEqual(
            first["files"]["server/requirements.txt"],
            third["files"]["server/requirements.txt"],
        )

    def test_secret_files_hidden_sources_and_external_symlinks_are_excluded(self):
        self.write("server/wakfu_server/combat/valid.py", "pass\n")
        self.write("server/.hidden/private.py", "sensitive\n")
        self.write("server/secrets/private.py", "sensitive\n")
        self.write("server/private.key", "sensitive\n")
        external = self.write("external/sensitive.py", "sensitive\n")
        (self.root / "server/linked.py").symlink_to(external)
        (self.root / "server/linked_directory").symlink_to(
            external.parent, target_is_directory=True
        )
        result = inventory.source_manifest(self.root)
        self.assertEqual(list(result["files"]), ["server/wakfu_server/combat/valid.py"])
        self.assertNotIn("sensitive", json.dumps(result))

    def test_public_code_names_describing_secrets_remain_complete(self):
        names = (
            "server/migrations/091_exploration_secret_access.sql",
            "server/tests/test_exploration_secrets.py",
            "server/tests/test_scheduler_credentials.py",
            "server/wakfu_server/characters/exploration_secrets.py",
            "server/wakfu_server/storage/scheduler_credentials.py",
        )
        for name in names:
            self.write(name, "public code")
        result = inventory.source_manifest(self.root)
        self.assertEqual(set(result["files"]), set(names))
        for name in (
            "sniffer/java/ExportExplorationSecrets.java",
            "sniffer/java/VerifyExplorationSecrets.java",
        ):
            self.assertTrue(inventory._safe_source_relative(name))
        self.assertFalse(inventory._safe_source_relative("server/secrets/private.py"))
        self.assertFalse(inventory._safe_source_relative("server/.env"))
        self.assertFalse(inventory._safe_source_relative("server/private.pem"))

    def test_fixture_inputs_and_service_assets_change_source_identity(self):
        names = (
            "server/tests/fixtures/scenario.json",
            "server/test-fixtures/combat/action.bin",
            "server/ai-service/tests/fixtures/oracle.json.gz",
            "server/admin-service/static/app.js",
            "server/admin-service/templates/fight.html",
        )
        for name in names:
            self.write(name, "before")
        for name in names:
            with self.subTest(name=name):
                before = inventory.source_manifest(self.root)
                self.assertIn(name, before["files"])
                (self.root / name).write_text("after", encoding="utf8")
                after = inventory.source_manifest(self.root)
                self.assertNotEqual(before["sha256"], after["sha256"])
                self.assertNotEqual(before["files"][name], after["files"][name])

    def test_validation_snapshot_verifies_and_pins_extra_inputs_without_private_roots(
        self,
    ):
        member = self.write("sniffer/java/NativeProbe.java", "class NativeProbe {}")
        manifest = {
            "source_root": "/private/workspace",
            "snapshot_root": "/private/snapshot",
            "files": {"sniffer/java/NativeProbe.java": inventory._hash_file(member)},
        }
        self.write("validation-snapshot.json", json.dumps(manifest))
        before = inventory.source_manifest(self.root)
        self.assertEqual(before["validation_snapshot"]["status"], "verified")
        self.assertIn("validation-snapshot.json", before["files"])
        self.assertIn("sniffer/java/NativeProbe.java", before["files"])
        self.assertNotIn("/private/", json.dumps(before))
        member.write_text("class NativeProbe { int changed; }")
        after = inventory.source_manifest(self.root)
        self.assertEqual(after["validation_snapshot"]["status"], "mismatch")
        self.assertEqual(after["validation_snapshot"]["mismatch_count"], 1)
        self.assertNotEqual(before["sha256"], after["sha256"])

    def test_validation_snapshot_rejects_external_symlinks_and_client_binaries(self):
        member = self.write("outside/file.py", "pass")
        target = self.root / "server/linked.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(member)
        for name in ("server/linked.py", "../outside.py", "client/official.bin"):
            with self.subTest(name=name):
                self.write(
                    "validation-snapshot.json", json.dumps({"files": {name: "a" * 64}})
                )
                result = inventory.source_manifest(self.root)
                self.assertEqual(result["validation_snapshot"]["status"], "invalid")
                self.assertNotIn(name, result["files"])

    def test_snapshot_accepts_only_declared_guide_input_and_verifies_its_bytes(self):
        name = "agents_docs/reports/combat-resilience-phase1-2/source-scenarios.json"
        member = self.write(name, '{"scenarios": []}')
        self.write(
            "validation-snapshot.json",
            json.dumps({"files": {name: inventory._hash_file(member)}}),
        )
        verified = inventory.source_manifest(self.root)
        self.assertEqual(verified["validation_snapshot"]["status"], "verified")
        self.assertEqual(verified["files"][name], inventory._hash_file(member))
        member.write_text('{"scenarios": [{"id": "changed"}]}')
        self.assertEqual(
            inventory.source_manifest(self.root)["validation_snapshot"]["status"],
            "mismatch",
        )
        private_name = (
            "agents_docs/reports/combat-resilience-phase1-2/private-report.json"
        )
        private = self.write(private_name, '{"private": true}')
        self.write(
            "validation-snapshot.json",
            json.dumps({"files": {private_name: inventory._hash_file(private)}}),
        )
        rejected = inventory.source_manifest(self.root)
        self.assertEqual(rejected["validation_snapshot"]["status"], "invalid")
        self.assertNotIn(private_name, rejected["files"])

    def test_git_identity_reports_counts_without_private_filenames(self):
        class Result:
            returncode = 0

            def __init__(self, stdout):
                self.stdout = stdout

        with patch.object(
            inventory.subprocess,
            "run",
            side_effect=[
                Result("a" * 40 + "\n"),
                Result("feature/combat\n"),
                Result(
                    " M private-credential.txt\0R  new-secret.txt\0old-secret.txt\0"
                ),
            ],
        ):
            result = inventory._git_identity(self.root)
        self.assertTrue(result["dirty"])
        self.assertEqual(result["changed_path_count"], 2)
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("credential", json.dumps(result))

    def test_catalog_published_identity_uses_native_authority(self):
        from wakfu_server import native_catalog

        documents = {"spells.json": "a" * 64, "states.json": "b" * 64}
        with patch.object(
            native_catalog, "release", return_value="rev-1"
        ), patch.object(native_catalog, "document_hashes", return_value=documents):
            result = inventory.catalog_manifest()
        self.assertEqual(result["status"], "published")
        self.assertTrue(result["publication_verified"])
        self.assertEqual(result["documents"], documents)
        self.assertEqual(len(result["sha256"]), 64)

    def test_catalog_failure_never_logs_exception_message_or_falls_back(self):
        from wakfu_server import native_catalog

        with patch.object(
            native_catalog,
            "release",
            side_effect=RuntimeError("postgres://password@private"),
        ):
            result = inventory.catalog_manifest()
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["error_type"], "RuntimeError")
        self.assertIsNone(result["sha256"])
        self.assertNotIn("password", json.dumps(result))
        self.assertNotIn("postgres", json.dumps(result))

    def test_catalog_identity_uses_actual_offline_patch_module_identity(self):
        from wakfu_server.combat_reproduction_catalog import _Patch

        class PinnedCatalog(_Patch):
            def release(self):
                return "offline-pinned"

            def document_hashes(self):
                return {"spells.json": "a" * 64}

            def __getattr__(self, name):
                return lambda *args, **kwargs: None

        with PinnedCatalog().install():
            result = inventory.catalog_manifest()
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["revision"], "offline-pinned")
        self.assertEqual(result["authority"], "wakfu_server.native_catalog")

    def test_offline_catalog_cannot_claim_publication(self):
        evidence = self.write(
            ".runtime/catalog.json",
            json.dumps(
                {
                    "revision": "rev-1",
                    "documents": {"spells.json": "a" * 64},
                    "publication_verified": True,
                    "status": "published",
                }
            ),
        )
        result = inventory.catalog_manifest(evidence)
        self.assertEqual(result["status"], "offline_unverified")
        self.assertFalse(result["publication_verified"])
        self.assertEqual(result["document_count"], 1)

    def test_offline_catalog_rejects_unsafe_paths_and_malformed_hashes(self):
        for documents in ({"../private.json": "a" * 64}, {"spells.json": "bad"}, {}):
            with self.subTest(documents=documents):
                evidence = self.write(
                    ".runtime/catalog.json",
                    json.dumps(
                        {
                            "revision": "rev-1",
                            "documents": documents,
                        }
                    ),
                )
                with self.assertRaises(ValueError):
                    inventory.catalog_manifest(evidence)

    def test_route_inventory_distinguishes_static_candidates_and_unknown_dispatch(self):
        self.write(
            "server/local_game_server.py",
            """def handle_spell():
    execute_spell()
    service.move_actor()
    def deferred():
        legacy_spell()

def execute_spell():
    return 1

def legacy_spell():
    return 2

def orphan_spell():
    return 3
""",
        )
        result = inventory.route_inventory(self.root)
        routes = {route["symbol"]: route for route in result["routes"]}
        self.assertEqual(
            routes["execute_spell"]["classification"], "referenced_static_candidate"
        )
        self.assertEqual(
            routes["legacy_spell"]["classification"], "compatibility_name_candidate"
        )
        self.assertEqual(
            routes["orphan_spell"]["classification"], "no_unqualified_caller_found"
        )
        caller = routes["legacy_spell"]["candidate_callers"][0]["caller"]
        self.assertTrue(caller.endswith(":handle_spell.deferred"))
        self.assertEqual(
            [call["expression"] for call in routes["handle_spell"]["calls"]],
            ["execute_spell", "service.move_actor"],
        )
        self.assertEqual(routes["handle_spell"]["calls"][1]["candidate_targets"], [])

    def test_inventory_detects_sources_changing_during_capture(self):
        first = {
            "sha256": "before",
            "files": {"a": "before"},
            "validation_snapshot": {"status": "absent"},
        }
        second = {
            "sha256": "after",
            "files": {"a": "after"},
            "validation_snapshot": {"status": "absent"},
        }
        with patch.object(
            inventory, "source_manifest", side_effect=[first, second]
        ), patch.object(inventory, "catalog_manifest", return_value={}), patch.object(
            inventory, "environment_manifest", return_value={}
        ), patch.object(
            inventory, "route_inventory", return_value={}
        ):
            result = inventory.build_inventory(self.root)
        self.assertFalse(result["source_stable"])
        self.assertEqual(result["source_after_sha256"], "after")

    def test_cli_rejects_output_outside_runtime(self):
        with self.assertRaises(SystemExit) as error:
            inventory.main(
                ["--root", str(self.root), "--output", str(self.root / "public.json")]
            )
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
