"""Frozen validation includes declared report inputs without private data."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


tool_path = Path(__file__).resolve().parents[1] / "tools/snapshot_combat_validation.py"
spec = importlib.util.spec_from_file_location("combat_validation_snapshot", tool_path)
snapshot_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot_tool)


class ValidationSnapshotTests(unittest.TestCase):
    def test_impact_scenario_input_is_frozen_without_other_internal_reports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            reports = root / "agents_docs/reports/combat-resilience-phase1-2"
            reports.mkdir(parents=True)
            source = reports / "source-scenarios.json"
            source.write_text('{"scenarios": [{"id": "fixture"}]}\n')
            (reports / "unrelated.json").write_text('{"private": true}\n')
            destination = Path(temporary) / "snapshot"
            snapshot_tool.snapshot(root, destination)
            frozen = destination / source.relative_to(root)
            self.assertEqual(frozen.read_bytes(), source.read_bytes())
            from tools.combat_baseline_inventory import source_manifest

            self.assertEqual(
                source_manifest(destination)["validation_snapshot"]["status"],
                "verified",
            )
            source.write_text("{}\n")
            self.assertIn('"fixture"', frozen.read_text())
            self.assertFalse(
                (destination / reports.relative_to(root) / "unrelated.json").exists()
            )
            source.unlink()
            source.symlink_to(reports / "unrelated.json")
            self.assertNotIn(source.relative_to(root), snapshot_tool.files(root))

    def test_movement_fixture_service_sources_are_frozen_without_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            tests = root / "server/tests"
            service = root / "server/ai-service"
            tests.mkdir(parents=True)
            service.mkdir(parents=True)
            (tests / "test_ai_service.py").write_text('SERVICE = "planner.py"\n')
            (service / "planner.py").write_text('POLICY = "original"\n')
            (service / "server.py").write_text('SERVICE = "offline fixture"\n')
            (service / ".env").write_text("PRIVATE_CONFIGURATION=true\n")
            (service / "unrelated.py").write_text("OTHER = True\n")
            package = service / "wakfu_ai/planning"
            package.mkdir(parents=True)
            (package / "planner.py").write_text('POLICY = "package source"\n')
            (package / "settings.json").write_text("{}\n")
            destination = Path(temporary) / "snapshot"
            snapshot_tool.snapshot(root, destination)
            (service / "planner.py").write_text('POLICY = "changed"\n')
            frozen = destination / "server/ai-service"
            self.assertEqual(
                (frozen / "planner.py").read_text(), 'POLICY = "original"\n'
            )
            self.assertTrue((frozen / "server.py").is_file())
            self.assertFalse((frozen / ".env").exists())
            self.assertFalse((frozen / "unrelated.py").exists())
            self.assertEqual(
                (frozen / "wakfu_ai/planning/planner.py").read_text(),
                'POLICY = "package source"\n',
            )
            self.assertFalse((frozen / "wakfu_ai/planning/settings.json").exists())

    def test_named_report_fixture_is_captured_and_remains_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            tests = root / "server/tests"
            reports = root / "docs/reports/combat-inventory"
            tests.mkdir(parents=True)
            reports.mkdir(parents=True)
            (tests / "test_fixture.py").write_text('INPUT = "active-cast-audit.json"\n')
            fixture = reports / "active-cast-audit.json"
            fixture.write_text('{"criteria": "HasState(55)"}\n')
            (reports / "unreferenced.json").write_text("{}\n")
            destination = Path(temporary) / "snapshot"
            snapshot_tool.snapshot(root, destination)
            captured = destination / fixture.relative_to(root)
            self.assertEqual(captured.read_bytes(), fixture.read_bytes())
            fixture.write_text("{}\n")
            self.assertEqual(captured.read_text(), '{"criteria": "HasState(55)"}\n')
            self.assertFalse(
                (
                    destination / "docs/reports/combat-inventory/" "unreferenced.json"
                ).exists()
            )

    def test_native_ai_test_fixtures_required_by_server_tests_are_included(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            tests = root / "server/tests"
            fixtures = root / "server/ai-service/tests/fixtures"
            tests.mkdir(parents=True)
            fixtures.mkdir(parents=True)
            (tests / "test_ai_service.py").write_text(
                "# Enables SDK fixture snapshot\n"
            )
            (fixtures.parent / "test_native_oracle.py").write_text(
                "NATIVE_FIXTURE = True\n"
            )
            (fixtures / "native.json").write_text('{"actor_id": 7}\n')
            private = Path(temporary) / "private.json"
            private.write_text('{"private": true}\n')
            (fixtures / "private.json").symlink_to(private)
            (fixtures / ".env").write_text("PRIVATE_CONFIGURATION=true\n")
            destination = Path(temporary) / "snapshot"
            snapshot_tool.snapshot(root, destination)
            captured = destination / "server/ai-service/tests"
            self.assertEqual(
                (captured / "test_native_oracle.py").read_text(),
                "NATIVE_FIXTURE = True\n",
            )
            self.assertTrue((captured / "fixtures/native.json").is_file())
            self.assertFalse((captured / "fixtures/private.json").exists())
            self.assertFalse((captured / "fixtures/.env").exists())

    def test_full_server_snapshot_contains_migrations_services_and_static_audit_sources(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            expected = {
                "server/migrations/001_initial.sql": "CREATE TABLE example(id integer);\n",
                "server/admin-service/service.py": "SERVICE = True\n",
                "server/admin-service/static/index.html": "<main>Example</main>\n",
                "server/test-fixtures/combat/example.json": "{}\n",
                "sniffer/audit-capture.py": "AUDIT = True\n",
                "client-tools/local-client.sh": "#!/bin/sh\n",
                "compose.yaml": "services: {}\n",
                "docs/example.md": "# Example\n",
            }
            for relative, contents in expected.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents)
            private = root / "server/admin-service/.env"
            private.write_text("PASSWORD=private\n")
            binary = root / "client/lib/wakfu-client.jar"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"client")
            outside = Path(temporary) / "private.py"
            outside.write_text("PRIVATE = True\n")
            (root / "server/admin-service/external.py").symlink_to(outside)
            destination = Path(temporary) / "snapshot"
            snapshot_tool.snapshot(root, destination, full_server=True)
            for relative, contents in expected.items():
                self.assertEqual((destination / relative).read_text(), contents)
            self.assertFalse((destination / private.relative_to(root)).exists())
            self.assertFalse((destination / binary.relative_to(root)).exists())
            self.assertFalse(
                (destination / "server/admin-service/external.py").exists()
            )

    def test_report_fixture_cannot_follow_symlink_into_private_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            tests = root / "server/tests"
            reports = root / "docs/reports/combat-inventory"
            tests.mkdir(parents=True)
            reports.mkdir(parents=True)
            (tests / "test_fixture.py").write_text('INPUT = "private.json"\n')
            private = Path(temporary) / "private.json"
            private.write_text('{"private": true}\n')
            (reports / "private.json").symlink_to(private)
            destination = Path(temporary) / "snapshot"
            snapshot_tool.snapshot(root, destination)
            self.assertFalse(
                (destination / "docs/reports/combat-inventory/" "private.json").exists()
            )

    def test_named_tsv_report_fixture_is_captured_without_unreferenced_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            tests = root / "server/tests"
            reports = root / "docs/reports/combat-inventory"
            tests.mkdir(parents=True)
            reports.mkdir(parents=True)
            (tests / "test_fixture.py").write_text(
                'INPUT = "native-cast-facing-probe.tsv"\n'
            )
            fixture = reports / "native-cast-facing-probe.tsv"
            fixture.write_text("direction\\tx\\ty\\tresult\\n")
            (reports / "unreferenced.tsv").write_text("private\\n")
            destination = Path(temporary) / "snapshot"
            snapshot_tool.snapshot(root, destination)
            captured = destination / fixture.relative_to(root)
            self.assertEqual(captured.read_text(), "direction\\tx\\ty\\tresult\\n")
            self.assertFalse(
                (
                    destination / "docs/reports/combat-inventory/" "unreferenced.tsv"
                ).exists()
            )

    def test_repo_report_path_is_captured_without_traversal_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            tests = root / "server/tests"
            reports = root / "docs/reports/combat-inventory"
            tests.mkdir(parents=True)
            reports.mkdir(parents=True)
            (tests / "test_fixture.py").write_text(
                'INPUT = "docs/reports/combat-inventory/ready-eca-deferred-runner-focal.json"\n'
                'EXCLUDED = "../docs/reports/combat-inventory/private.json"\n'
            )
            (reports / "ready-eca-deferred-runner-focal.json").write_text("{}\n")
            (reports / "private.json").write_text("{}\n")
            destination = Path(temporary) / "snapshot"
            snapshot_tool.snapshot(root, destination)
            self.assertTrue(
                (
                    destination / "docs/reports/combat-inventory/"
                    "ready-eca-deferred-runner-focal.json"
                ).is_file()
            )
            self.assertFalse(
                (destination / "docs/reports/combat-inventory/" "private.json").exists()
            )


if __name__ == "__main__":
    unittest.main()
