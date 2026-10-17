"""Behavioral selector contracts; fixtures never import or execute engine code."""
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.combat_baseline_inventory import canonical_digest
from tools.combat_test_impact import (
    build_graph,
    compare_shadow,
    main,
    runtime_policy_inputs,
    select_changes,
)


class ImpactGraphTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.write("server/tools/combat_validation_profile.py", "# fixture runner\n")
        self.catalog = {
            "status": "published",
            "revision": "fixture",
            "documents": {},
            "sha256": "a" * 64,
            "publication_verified": True,
        }
        environment = patch(
            "tools.combat_test_impact.environment_manifest",
            return_value={"sha256": "e" * 64},
        )
        environment.start()
        self.addCleanup(environment.stop)

    def write(self, name, body):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)

    def graph(self, catalog=None, scenarios=None):
        return build_graph(
            self.root, catalog_inventory=catalog or self.catalog, scenarios=scenarios
        )

    @contextmanager
    def semantic_reviews(self, classifications=None, accepted=None):
        from tools.combat_test_impact import CONTRACTS_PATH

        contracts = json.loads(CONTRACTS_PATH.read_bytes())
        if classifications is not None:
            contracts["test_classifications"] = classifications
        if accepted is not None:
            contracts["accepted_scenarios"] = accepted
        path = self.root / "fixture-semantic-contracts.json"
        path.write_text(json.dumps(contracts))
        with patch("tools.combat_test_impact.CONTRACTS_PATH", path):
            yield

    def file_sha(self, path):
        return hashlib.sha256((self.root / path).read_bytes()).hexdigest()

    def review(self, path, kind="contract", witnesses=None, **extra):
        return {
            "path": path,
            "source_sha256": self.file_sha(path),
            "kind": kind,
            "scope": "Only the explicitly reviewed fixture entry point.",
            "rationale": "Source-bound fixture classification, not a passing execution.",
            "assertion_witnesses": witnesses or [],
            **extra,
        }

    def changed_graph(self, graph, identity):
        changed = copy.deepcopy(graph)
        row = next(row for row in changed["nodes"] if row["id"] == identity)
        row["sha256"] = "f" * 64
        changed["provenance"]["source_manifest_sha256"] = "b" * 64
        changed["sha256"] = canonical_digest(
            {k: v for k, v in changed.items() if k != "sha256"}
        )
        return changed

    def full_report(self, graph):
        provenance = graph["provenance"]
        endpoint = {
            "source": {"sha256": provenance["source_manifest_sha256"]},
            "catalog": {
                "sha256": provenance["catalog_inventory_sha256"],
                "revision": provenance["catalog_revision"],
                "publication_verified": True,
            },
            "environment": {"sha256": provenance["environment_sha256"]},
        }
        inputs = {
            key: provenance[key]
            for key in (
                "scenario_manifest_sha256",
                "contracts_sha256",
                "builder_sha256",
                "runtime_policy_sha256",
                "runtime_policy_names",
            )
        }
        return {
            "provenance_before": copy.deepcopy(endpoint),
            "provenance_after": copy.deepcopy(endpoint),
            "provenance_stable": True,
            "runner": {
                "sha256": provenance["runner_sha256"],
                "policy": provenance["runner_policy"],
            },
            "impact_inputs_before": copy.deepcopy(inputs),
            "impact_inputs_after": copy.deepcopy(inputs),
            "discovery": {"module_names": graph["module_names"]},
            "module_timing": {
                name: {
                    "status": "completed",
                    "origin": "executed",
                    "return_code": 0,
                    "discovery": {"tests": 1},
                    "result": {
                        "successful": True,
                        "failures": 0,
                        "errors": 0,
                        "unexpected_successes": 0,
                        "tests_run": 1,
                        "skipped": 0,
                        "expected_failures": 0,
                    },
                }
                for name in graph["module_names"]
            },
        }

    def test_all_server_modules_and_flattened_relative_imports(self):
        self.write("server/wakfu_server/combat/primitive.py", "VALUE = 1\n")
        self.write(
            "server/wakfu_server/combat/wrapper.py",
            "from .primitive import VALUE as value\n",
        )
        self.write(
            "server/tests/test_combat_user.py",
            "from wakfu_server.wrapper import value\n",
        )
        self.write("server/tests/test_admin_user.py", "import unittest\n")
        self.write("server/tests/test_storage_user.py", "import unittest\n")
        before = self.graph()
        self.write("server/wakfu_server/combat/primitive.py", "VALUE = 2\n")
        plan = select_changes(before, self.graph())
        self.assertEqual(
            before["module_names"],
            ["test_admin_user", "test_combat_user", "test_storage_user"],
        )
        self.assertEqual(plan["selected_module_names"], ["test_combat_user"])
        self.assertFalse(plan["suppression_enabled"])
        self.assertTrue(plan["explanations"]["test_combat_user"]["path"])

    def test_deleted_dependency_retains_old_consumers(self):
        self.write("server/wakfu_server/combat/primitive.py", "VALUE = 1\n")
        self.write(
            "server/tests/test_consumer.py",
            "from wakfu_server.primitive import VALUE\n",
        )
        self.write("server/tests/test_unrelated.py", "import unittest\n")
        before = self.graph()
        (self.root / "server/wakfu_server/combat/primitive.py").unlink()
        self.write("server/tests/test_consumer.py", "import unittest\n")
        plan = select_changes(before, self.graph())
        self.assertIn("test_consumer", plan["selected_module_names"])
        self.assertNotIn("test_unrelated", plan["selected_module_names"])

    def test_alias_module_and_multihop_inherited_fixture_and_test(self):
        self.write(
            "server/tests/postgres_case.py",
            "import unittest\nclass PostgresCase(unittest.TestCase):\n def setUp(self): pass\n def test_shared(self): pass\n",
        )
        self.write(
            "server/tests/test_base.py",
            "from postgres_case import PostgresCase\nclass Base(PostgresCase): pass\n",
        )
        self.write(
            "server/tests/test_child.py",
            "import test_base as fixtures\nclass Child(fixtures.Base): pass\n",
        )
        self.write(
            "server/tests/test_grandchild.py",
            "import test_child as fixtures\nclass Grandchild(fixtures.Child): pass\n",
        )
        self.write("server/tests/test_other.py", "import unittest\n")
        before = self.graph()
        self.write("server/migrations/001.sql", "CREATE TABLE example (id integer);\n")
        after = self.graph()
        plan = select_changes(before, after)
        self.assertEqual(
            plan["selected_module_names"],
            ["test_base", "test_child", "test_grandchild"],
        )
        inherited = next(
            row
            for row in after["nodes"]
            if row["id"]
            == "method:server/tests/test_grandchild.py:Grandchild.test_shared"
        )
        self.assertEqual(inherited["discovery"], "inherited-static-unconfirmed")

    def test_catalog_aliases_are_canonical_and_document_scoped(self):
        self.write(
            "server/tests/test_first.py",
            'from wakfu_server.storage import native_catalog as cat\nfrom wakfu_server.paths import DATA_ROOT\nDATA = cat.load(DATA_ROOT / "first.json")\n',
        )
        self.write(
            "server/tests/test_second.py",
            'from wakfu_server import native_catalog as cat\nfrom wakfu_server.paths import DATA_ROOT\nDATA = cat.load(DATA_ROOT / "second.json")\n',
        )
        # Minimal actual canonical files make both spellings resolvable.
        self.write(
            "server/wakfu_server/storage/native_catalog.py", "def load(path): pass\n"
        )
        self.write("server/wakfu_server/paths.py", "DATA_ROOT = None\n")
        catalog = copy.deepcopy(self.catalog)
        catalog["documents"] = {"first.json": "1" * 64, "second.json": "2" * 64}
        before = self.graph(catalog)
        catalog["documents"]["first.json"] = "3" * 64
        catalog["sha256"] = "c" * 64
        plan = select_changes(before, self.graph(catalog))
        self.assertEqual(plan["selected_module_names"], ["test_first"])
        dependencies = {
            edge["dependency"]
            for edge in before["edges"]
            if edge["consumer"] == "module:server/tests/test_first.py"
        }
        self.assertIn(
            "module:server/wakfu_server/storage/native_catalog.py", dependencies
        )
        self.assertIn("catalog:first.json", dependencies)

    def test_local_discovery_hook_is_bounded_and_missing_before_still_full(self):
        self.write(
            "server/tests/test_dynamic.py",
            "def load_tests(loader, tests, pattern): return tests\n",
        )
        self.write("server/tests/test_other.py", "import unittest\n")
        before = self.graph()
        self.write(
            "server/tests/test_dynamic.py",
            "def load_tests(loader, tests, pattern): return None\n",
        )
        plan = select_changes(before, self.graph())
        self.assertEqual(plan["selected_module_names"], ["test_dynamic"])
        self.assertTrue(
            any(
                row["reason"] == "dynamic-test-discovery"
                and row["scope"] == "owner-consumers"
                for row in plan["fallbacks"]
            )
        )
        self.assertEqual(
            select_changes(None, before)["selected_module_names"],
            before["module_names"],
        )

    def test_indirect_loader_hook_selects_exposing_tests_without_global_fallback(self):
        import os
        import subprocess
        import sys

        self.write(
            "server/hidden_case.py",
            "import unittest\nVALUE = 1\nclass LoadedTests(unittest.TestCase):\n def test_value(self): self.assertEqual(VALUE, 1)\n",
        )
        self.write(
            "server/tests/test_hook.py",
            'def load_tests(loader, tests, pattern):\n prefix = "hidden_"\n suffix = "case.LoadedTests"\n return loader.loadTestsFromName(prefix + suffix)\n',
        )
        self.write("server/tests/test_other.py", "import unittest\n")
        environment = os.environ.copy()
        environment.update(
            PYTHONPATH=str(self.root / "server"), PYTHONDONTWRITEBYTECODE="1"
        )
        command = [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(self.root / "server/tests"),
            "-p",
            "test_hook.py",
        ]
        before_run = subprocess.run(
            command,
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(before_run.returncode, 0, before_run.stderr)
        before = self.graph()
        self.write(
            "server/hidden_case.py",
            "import unittest\nVALUE = 2\nclass LoadedTests(unittest.TestCase):\n def test_value(self): self.assertEqual(VALUE, 1)\n",
        )
        after = self.graph()
        plan = select_changes(before, after)
        self.assertEqual(plan["selected_module_names"], ["test_hook"])
        self.assertTrue(
            any(row["reason"] == "dynamic-test-discovery" for row in plan["unknowns"])
        )
        self.assertFalse(any(row["scope"] == "full" for row in plan["fallbacks"]))
        self.assertEqual(set(after["module_names"]), {"test_hook", "test_other"})
        after_run = subprocess.run(
            command,
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(after_run.returncode, 1, after_run.stderr)
        self.assertIn("2 != 1", after_run.stderr)

    def test_unrelated_unknown_does_not_expand_qualified_edit(self):
        self.write("server/wakfu_server/combat/primitive.py", "VALUE = 1\n")
        self.write(
            "server/tests/test_consumer.py",
            "from wakfu_server.primitive import VALUE\n",
        )
        self.write("server/tests/test_dynamic.py", "class Derived(UnknownBase): pass\n")
        before = self.graph()
        self.write("server/wakfu_server/combat/primitive.py", "VALUE = 2\n")
        plan = select_changes(before, self.graph())
        self.assertEqual(plan["selected_module_names"], ["test_consumer"])

    def test_oracle_only_change_and_scenario_partial_mapping(self):
        self.write("server/tests/test_combat_state_cleanup.py", "import unittest\n")
        self.write(
            "server/tests/fixtures/native_state_cleanup_982.json", '{"order": [1, 2]}'
        )
        self.write("server/tests/test_other.py", "import unittest\n")
        scenarios = {
            "sources": [{"id": "player", "url": "https://example.test"}],
            "scenarios": [
                {
                    "id": "intent",
                    "source_ids": ["player"],
                    "mapping_evidence": ["server/tests/test_combat_state_cleanup.py"],
                    "unresolved": ["native mask"],
                }
            ],
        }
        before = self.graph(scenarios=scenarios)
        self.write(
            "server/tests/fixtures/native_state_cleanup_982.json", '{"order": [2, 1]}'
        )
        plan = select_changes(before, self.graph(scenarios=scenarios))
        self.assertEqual(plan["selected_module_names"], ["test_combat_state_cleanup"])
        self.assertTrue(
            any(
                row["reason"] == "partial-native-scenario-mapping"
                for row in before["unknowns"]
            )
        )

    def test_shadow_preserves_outside_historical_failure_without_regression_claim(self):
        self.write("server/tests/test_inside.py", "import unittest\n")
        self.write("server/tests/test_outside.py", "import unittest\n")
        before = self.graph()
        after = self.changed_graph(before, "module:server/tests/test_inside.py")
        plan = select_changes(before, after)
        report = self.full_report(after)
        report["module_timing"]["test_outside"] = {
            "status": "completed",
            "origin": "executed",
            "return_code": 1,
            "result": {"successful": False, "failures": 1},
        }
        result = compare_shadow(plan, report)
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["outside_subset_nonpasses"], ["test_outside"])
        self.assertEqual(result["regression_attribution"], "not-established")

    def test_shadow_rejects_identity_drift_missing_fields_and_partial_reports(self):
        self.write("server/tests/test_one.py", "import unittest\n")
        graph = self.graph()
        plan = select_changes(None, graph)
        for field in ("source", "catalog", "environment"):
            report = self.full_report(graph)
            report["provenance_after"][field]["sha256"] = "z" * 64
            self.assertEqual(compare_shadow(plan, report)["status"], "incompatible")
        report = self.full_report(graph)
        report["runner"]["sha256"] = "z" * 64
        self.assertEqual(compare_shadow(plan, report)["status"], "incompatible")
        report = self.full_report(graph)
        report["impact_inputs_after"]["scenario_manifest_sha256"] = "z" * 64
        self.assertEqual(compare_shadow(plan, report)["status"], "incompatible")
        report.pop("impact_inputs_before")
        self.assertEqual(compare_shadow(plan, report)["status"], "unavailable")
        report = self.full_report(graph)
        report["module_timing"] = {}
        self.assertEqual(compare_shadow(plan, report)["status"], "unavailable")

    def test_shadow_reused_result_retains_origin_without_fresh_execution_claim(self):
        self.write("server/tests/test_inside.py", "import unittest\n")
        self.write("server/tests/test_outside.py", "import unittest\n")
        before = self.graph()
        after = self.changed_graph(before, "module:server/tests/test_inside.py")
        plan = select_changes(before, after)
        report = self.full_report(after)
        cached = report["module_timing"]["test_outside"]
        cached.update(status="reused", origin="reused", return_code=None)
        cached["result"].update(tests_run=0, tests_verified=1, reused_tests=1)
        result = compare_shadow(plan, report)
        outcome = next(
            row for row in result["outcomes"] if row["module"] == "test_outside"
        )
        self.assertEqual(outcome["status"], "reused-not-fresh")
        self.assertEqual(outcome["origin"], "reused")
        self.assertIn("test_outside", result["outside_subset_nonpasses"])
        self.assertEqual(result["regression_attribution"], "not-established")

    def test_shadow_completed_result_requires_explicit_fresh_origin(self):
        self.write("server/tests/test_one.py", "import unittest\n")
        graph = self.graph()
        plan = select_changes(None, graph)
        for origin in (None, "reused", "unrecognized"):
            with self.subTest(origin=origin):
                report = self.full_report(graph)
                item = report["module_timing"]["test_one"]
                if origin is None:
                    item.pop("origin")
                else:
                    item["origin"] = origin
                outcome = compare_shadow(plan, report)["outcomes"][0]
                self.assertEqual(outcome["status"], "inconsistent-terminal-report")
                self.assertEqual(outcome["origin"], origin or "unknown")
        report = self.full_report(graph)
        report["module_timing"]["test_one"]["result"]["reused_tests"] = 1
        self.assertEqual(
            compare_shadow(plan, report)["outcomes"][0]["status"],
            "inconsistent-terminal-report",
        )
        fresh = compare_shadow(plan, self.full_report(graph))["outcomes"][0]
        self.assertEqual(fresh["status"], "terminal-pass")
        self.assertEqual(fresh["origin"], "executed")

    def test_boolean_terminal_exit_code_is_malformed_not_a_passing_process(self):
        self.write("server/tests/test_one.py", "import unittest\n")
        graph = self.graph()
        plan = select_changes(None, graph)
        report = self.full_report(graph)
        report["module_timing"]["test_one"]["return_code"] = False
        outcome = compare_shadow(plan, report)["outcomes"][0]
        self.assertEqual(outcome["status"], "inconsistent-terminal-report")
        self.assertNotEqual(outcome["status"], "terminal-pass")

    def test_direct_catalog_function_alias_and_bare_record_literal(self):
        self.write(
            "server/wakfu_server/storage/native_catalog.py",
            "def read_bytes(path): pass\ndef record(path, collection, key): pass\n",
        )
        self.write(
            "server/tests/test_alias.py",
            'from wakfu_server.native_catalog import read_bytes as catalog_bytes, record as get_record\nvalue = catalog_bytes("native-example.json")\nrecord = get_record("native-example.json", "spells", 42)\n',
        )
        graph = self.graph()
        dependencies = {
            edge["dependency"]
            for edge in graph["edges"]
            if edge["consumer"] == "module:server/tests/test_alias.py"
        }
        self.assertIn("catalog:native-example.json", dependencies)
        self.assertIn("catalog:native-example.json:record:spells:42", dependencies)
        self.assertFalse(
            any(row["reason"] == "dynamic-catalog-path" for row in graph["unknowns"])
        )

    def test_reviewed_kinds_require_current_source_and_real_review_locators(self):
        path = "server/tests/test_reviewed.py"
        self.write(
            path,
            "import unittest\nclass Reviewed(unittest.TestCase):\n def test_contract(self): self.assertEqual(1, 1)\n",
        )
        declaration = self.review(path, witnesses=["Reviewed.test_contract"])
        with self.semantic_reviews([declaration]):
            graph = self.graph()
        reviewed = next(
            row for row in graph["nodes"] if row["id"] == "test-module:" + path
        )
        self.assertEqual(reviewed["test_kind"], "contract")
        self.assertEqual(
            reviewed["classification_review"]["status"], "verified-source-review"
        )
        mutations = (
            {"source_sha256": "f" * 64},
            {"assertion_witnesses": ["Reviewed.test_missing"]},
            {"scope": ""},
            {"rationale": ""},
            {"kind": "invented"},
            {"assertion_witnesses": []},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                invalid = {**declaration, **mutation}
                with self.semantic_reviews([invalid]):
                    graph = self.graph()
                reviewed = next(
                    row for row in graph["nodes"] if row["id"] == "test-module:" + path
                )
                self.assertEqual(reviewed["test_kind"], "unknown")
                self.assertTrue(reviewed["classification_review"]["errors"])
        with self.semantic_reviews([declaration, declaration]):
            graph = self.graph()
        reviewed = next(
            row for row in graph["nodes"] if row["id"] == "test-module:" + path
        )
        self.assertIn(
            "duplicate-classification-reviews",
            reviewed["classification_review"]["errors"],
        )

    def test_source_bound_inheritance_review_requires_actual_fixture_and_edge(self):
        base = "server/tests/postgres_case.py"
        path = "server/tests/test_child.py"
        self.write(
            base,
            "import unittest\nclass PostgresCase(unittest.TestCase):\n def setUp(self): pass\n",
        )
        self.write(
            path,
            "from postgres_case import PostgresCase\nclass Child(PostgresCase): pass\n",
        )
        evidence = {
            "base_path": base,
            "base_class": "PostgresCase",
            "source_sha256": self.file_sha(base),
            "fixture_methods": ["setUp"],
        }
        declaration = self.review(
            path, kind="integration", inheritance_evidence=[evidence]
        )
        with self.semantic_reviews([declaration]):
            graph = self.graph()
        reviewed = next(
            row for row in graph["nodes"] if row["id"] == "test-module:" + path
        )
        self.assertEqual(reviewed["test_kind"], "integration")
        declaration["inheritance_evidence"][0]["source_sha256"] = "f" * 64
        with self.semantic_reviews([declaration]):
            graph = self.graph()
        reviewed = next(
            row for row in graph["nodes"] if row["id"] == "test-module:" + path
        )
        self.assertEqual(reviewed["test_kind"], "unknown")
        with self.semantic_reviews([]):
            graph = self.graph()
        reviewed = next(
            row for row in graph["nodes"] if row["id"] == "test-module:" + path
        )
        self.assertEqual(reviewed["test_kind"], "unknown")

    def test_support_only_is_source_bound_zero_case_metadata_not_behavioral_pass(self):
        path = "server/tests/test_support.py"
        self.write(path, "class MemoryRedis:\n def ping(self): return True\n")
        declaration = self.review(
            path, kind="support-only", support_symbols=["MemoryRedis"]
        )
        with self.semantic_reviews([declaration], []):
            graph = self.graph()
        reviewed = next(
            row for row in graph["nodes"] if row["id"] == "test-module:" + path
        )
        self.assertEqual(reviewed["test_kind"], "support-only")
        self.assertEqual(graph["classification_summary"]["support-only"], 1)
        plan = select_changes(None, graph)
        report = self.full_report(graph)
        report["module_timing"]["test_support"]["discovery"]["tests"] = 0
        report["module_timing"]["test_support"]["result"]["tests_run"] = 0
        self.assertEqual(
            compare_shadow(plan, report)["outcomes"][0]["status"],
            "completed-with-unverified-cases",
        )
        self.write(
            path,
            "import unittest\nclass MemoryRedis(unittest.TestCase):\n def test_behavior(self): self.assertTrue(True)\n",
        )
        declaration["source_sha256"] = self.file_sha(path)
        with self.semantic_reviews([declaration], []):
            graph = self.graph()
        reviewed = next(
            row for row in graph["nodes"] if row["id"] == "test-module:" + path
        )
        self.assertEqual(reviewed["test_kind"], "unknown")
        self.assertTrue(reviewed["classification_review"]["errors"])

    def bounded_scenario_fixture(self):
        test_path = "server/tests/test_qualified.py"
        implementation = "server/wakfu_server/combat/combat_state_fixture.py"
        self.write(
            test_path,
            "import unittest\nclass Qualified(unittest.TestCase):\n def test_grant(self): self.assertEqual(1, 1)\n",
        )
        self.write(implementation, "VALUE = 1\n")
        scenario = {
            "id": "qualified",
            "source_ids": ["guide"],
            "intent": "One bounded interaction",
            "status": "candidate",
        }
        scenarios = {
            "sources": [{"id": "guide", "url": "https://example.test/guide"}],
            "scenarios": [
                {"id": "candidate", "source_ids": ["guide"], "status": "candidate"},
                scenario,
            ],
        }
        native_path = "server/tests/fixtures/native-guide-proof.json"
        native = {
            "schema": "wakemu-guide-native-interaction-evidence-v1",
            "scenario_id": "qualified",
            "guide_source": {"id": "guide", "url": "https://example.test/guide"},
            "native_documents": {"fixture-doc.json": {"sha256": "1" * 64}},
            "target_identity": {
                "installed_jar_sha256": "0" * 64,
                "native_export_jar_provenance_match": True,
                "published_catalog_revision": "fixture",
            },
            "test_contract": {
                "path": test_path,
                "source_sha256": self.file_sha(test_path),
            },
        }
        self.write(native_path, json.dumps(native))
        receipt_path = "server/tests/fixtures/passing-guide-proof.json"
        test_id = "test_qualified.Qualified.test_grant"
        receipt = {
            "schema": "wakemu-bounded-scenario-pass-v1",
            "scenario_id": "qualified",
            "terminal_status": "passed",
            "return_code": 0,
            "successful": True,
            "tests_run": 1,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
            "unexpected_successes": 0,
            "expected_failures": 0,
            "native_runtime_enabled": True,
            "test_ids": [test_id],
            "test_sources": {test_path: self.file_sha(test_path)},
            "engine_sources": {implementation: self.file_sha(implementation)},
            "catalog_revision": "fixture",
            "catalog_documents": {"fixture-doc.json": "1" * 64},
            "oracle_identity": {"installed_jar_sha256": "0" * 64},
        }
        self.write(receipt_path, json.dumps(receipt))
        declaration = {
            "id": "qualified",
            "source_scenario_id": "qualified",
            "source_scenario_sha256": canonical_digest(scenario),
            "source_ids": ["guide"],
            "scope": "Only the explicitly proven fixture interaction.",
            "rationale": "A validator fixture; not an actual native game execution.",
            "limitations": ["No whole guide or rendering proof"],
            "operation_ids": ["states"],
            "implementation_dependencies": {
                implementation: self.file_sha(implementation)
            },
            "test_dependencies": [
                {
                    "path": test_path,
                    "source_sha256": self.file_sha(test_path),
                    "assertion_witnesses": ["Qualified.test_grant"],
                }
            ],
            "native_evidence": [
                {
                    "path": native_path,
                    "sha256": self.file_sha(native_path),
                    "role": "native-mapping",
                }
            ],
            "passing_evidence": [
                {
                    "path": receipt_path,
                    "sha256": self.file_sha(receipt_path),
                    "test_ids": [test_id],
                }
            ],
        }
        catalog = {**self.catalog, "documents": {"fixture-doc.json": "1" * 64}}
        return scenarios, declaration, catalog, receipt

    def test_accepted_bounded_scenario_requires_all_source_native_and_terminal_proofs(
        self,
    ):
        scenarios, declaration, catalog, _ = self.bounded_scenario_fixture()
        with self.semantic_reviews([], [declaration]):
            graph = self.graph(catalog=catalog, scenarios=scenarios)
        accepted = next(
            row for row in graph["nodes"] if row["id"] == "scenario:qualified"
        )
        candidate = next(
            row for row in graph["nodes"] if row["id"] == "scenario:candidate"
        )
        self.assertEqual(accepted["acceptance_status"], "qualified-bounded-interaction")
        self.assertEqual(candidate["acceptance_status"], "unqualified-source-scenario")
        self.assertEqual(graph["accepted_scenario_count"], 1)
        self.assertTrue(
            any(
                row["kind"] == "asserts-bounded-guide-interaction"
                for row in graph["edges"]
            )
        )
        self.assertTrue(
            any(row["kind"] == "bounded-native-document" for row in graph["edges"])
        )

    def test_missing_or_stale_bounded_scenario_proofs_stay_candidates(self):
        scenarios, declaration, catalog, _ = self.bounded_scenario_fixture()
        mutations = (
            {"passing_evidence": []},
            {"source_scenario_sha256": "f" * 64},
            {"scope": ""},
            {"native_evidence": []},
            {"implementation_dependencies": {}},
            {"test_dependencies": []},
            {"source_ids": ["missing-guide"]},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.semantic_reviews([], [{**declaration, **mutation}]):
                    graph = self.graph(catalog=catalog, scenarios=scenarios)
                accepted = next(
                    row for row in graph["nodes"] if row["id"] == "scenario:qualified"
                )
                self.assertEqual(
                    accepted["acceptance_status"], "unqualified-source-scenario"
                )
                self.assertTrue(accepted["acceptance_review"]["errors"])
                self.assertEqual(graph["accepted_scenario_count"], 0)
        self.write(
            "server/tests/test_qualified.py",
            "import unittest\nclass Qualified(unittest.TestCase):\n def test_grant(self): self.assertEqual(2, 2)\n",
        )
        with self.semantic_reviews([], [declaration]):
            graph = self.graph(catalog=catalog, scenarios=scenarios)
        accepted = next(
            row for row in graph["nodes"] if row["id"] == "scenario:qualified"
        )
        self.assertEqual(accepted["acceptance_status"], "unqualified-source-scenario")

    def test_bounded_scenario_never_accepts_skipped_partial_or_wrong_native_receipts(
        self,
    ):
        scenarios, declaration, catalog, receipt = self.bounded_scenario_fixture()
        mutations = (
            {"skipped": 1},
            {"tests_run": 0},
            {"return_code": 143},
            {"oracle_identity": {"installed_jar_sha256": "2" * 64}},
            {"catalog_documents": {"fixture-doc.json": "3" * 64}},
            {"engine_sources": {}},
        )
        receipt_path = declaration["passing_evidence"][0]["path"]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.write(receipt_path, json.dumps({**receipt, **mutation}))
                changed = copy.deepcopy(declaration)
                changed["passing_evidence"][0]["sha256"] = self.file_sha(receipt_path)
                with self.semantic_reviews([], [changed]):
                    graph = self.graph(catalog=catalog, scenarios=scenarios)
                accepted = next(
                    row for row in graph["nodes"] if row["id"] == "scenario:qualified"
                )
                self.assertEqual(
                    accepted["acceptance_status"], "unqualified-source-scenario"
                )
                self.assertTrue(accepted["acceptance_review"]["errors"])

    def test_provider_injection_and_reviewed_classifications_are_explicit(self):
        self.write(
            "server/wakfu_server/combat/combat_effect_runtime.py",
            "class NativeRuntimeContexts:\n actor_candidates: object\n",
        )
        self.write(
            "server/wakfu_server/combat/combat_runtime_adapter.py",
            "from .combat_effect_runtime import NativeRuntimeContexts\ndef build(self): return NativeRuntimeContexts(actor_candidates=self.dynamic)\n",
        )
        self.write(
            "server/tests/test_combat_native_action_ids.py",
            "import unittest\nclass NativeActionIdTests(unittest.TestCase):\n def test_unique_actions_preserve_payload_identity_and_turn_ack(self): pass\n",
        )
        classification = self.review(
            "server/tests/test_combat_native_action_ids.py",
            witnesses=[
                "NativeActionIdTests.test_unique_actions_preserve_payload_identity_and_turn_ack"
            ],
        )
        with self.semantic_reviews([classification]):
            graph = self.graph()
        self.assertTrue(
            any(
                row["id"] == "provider-slot:NativeRuntimeContexts.actor_candidates"
                for row in graph["nodes"]
            )
        )
        self.assertTrue(
            any(
                row["reason"] == "injected-provider-expression"
                for row in graph["unknowns"]
            )
        )
        test = next(
            row
            for row in graph["nodes"]
            if row["id"] == "test-module:server/tests/test_combat_native_action_ids.py"
        )
        self.assertEqual(test["test_kind"], "contract")
        self.assertTrue(test["classification_evidence"])

    def test_real_class_setup_failure_is_terminal_nonpass_before_any_test_starts(self):
        import io

        class FailingSetup(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise FileNotFoundError("isolated fixture intentionally absent")

            def test_first(self):
                self.fail("setup must prevent execution")

            def test_second(self):
                self.fail("setup must prevent execution")

            def test_third(self):
                self.fail("setup must prevent execution")

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(FailingSetup)
        discovered = suite.countTestCases()
        actual = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        self.assertEqual((discovered, actual.testsRun, len(actual.errors)), (3, 0, 1))
        self.write("server/tests/test_setup.py", "import unittest\n")
        graph = self.graph()
        plan = select_changes(None, graph)
        report = self.full_report(graph)
        report["module_timing"]["test_setup"] = {
            "status": "completed",
            "origin": "executed",
            "return_code": 1,
            "discovery": {"tests": discovered},
            "result": {
                "successful": actual.wasSuccessful(),
                "tests_run": actual.testsRun,
                "failures": len(actual.failures),
                "errors": len(actual.errors),
                "unexpected_successes": len(actual.unexpectedSuccesses),
                "expected_failures": len(actual.expectedFailures),
                "skipped": len(actual.skipped),
            },
        }
        outcome = compare_shadow(plan, report)["outcomes"][0]
        self.assertEqual(outcome["status"], "terminal-nonpass")
        self.assertEqual(outcome["result"]["errors"], 1)

    def test_real_class_setup_skip_is_unverified_without_becoming_terminal_pass(self):
        import io

        class SkippedSetup(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise unittest.SkipTest("isolated backend intentionally unavailable")

            def test_first(self):
                self.fail("setup skip must prevent execution")

            def test_second(self):
                self.fail("setup skip must prevent execution")

            def test_third(self):
                self.fail("setup skip must prevent execution")

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SkippedSetup)
        discovered = suite.countTestCases()
        actual = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        self.assertEqual((discovered, actual.testsRun, len(actual.skipped)), (3, 0, 1))
        self.assertTrue(actual.wasSuccessful())
        self.write("server/tests/test_skipped.py", "import unittest\n")
        graph = self.graph()
        plan = select_changes(None, graph)
        report = self.full_report(graph)
        report["module_timing"]["test_skipped"] = {
            "status": "completed",
            "origin": "executed",
            "return_code": 0,
            "discovery": {"tests": discovered},
            "result": {
                "successful": actual.wasSuccessful(),
                "tests_run": actual.testsRun,
                "failures": len(actual.failures),
                "errors": len(actual.errors),
                "unexpected_successes": len(actual.unexpectedSuccesses),
                "expected_failures": len(actual.expectedFailures),
                "skipped": len(actual.skipped),
            },
        }
        outcome = compare_shadow(plan, report)["outcomes"][0]
        self.assertEqual(outcome["status"], "completed-with-unverified-cases")
        self.assertNotEqual(outcome["status"], "terminal-pass")
        report["module_timing"]["test_skipped"]["result"].update(
            skipped=0, expected_failures=1
        )
        self.assertEqual(
            compare_shadow(plan, report)["outcomes"][0]["status"],
            "inconsistent-terminal-report",
        )

    def test_partial_fake_green_remains_inconsistent_and_never_terminal_pass(self):
        self.write("server/tests/test_partial.py", "import unittest\n")
        graph = self.graph()
        plan = select_changes(None, graph)
        report = self.full_report(graph)
        report["module_timing"]["test_partial"]["discovery"]["tests"] = 3
        report["module_timing"]["test_partial"]["result"]["tests_run"] = 0
        outcome = compare_shadow(plan, report)["outcomes"][0]
        self.assertEqual(outcome["status"], "inconsistent-terminal-report")

    def test_shadow_success_flag_cannot_hide_failure_or_bad_count(self):
        self.write("server/tests/test_one.py", "import unittest\n")
        graph = self.graph()
        plan = select_changes(None, graph)
        for change in ({"failures": 1}, {"tests_run": 0}, {"unexpected_successes": 1}):
            with self.subTest(change=change):
                report = self.full_report(graph)
                report["module_timing"]["test_one"]["result"].update(change)
                result = compare_shadow(plan, report)
                self.assertNotEqual(result["outcomes"][0]["status"], "terminal-pass")

    def test_parameterized_reader_preserves_literal_and_unknown_callers(self):
        self.write(
            "server/tools/fixture_reader.py",
            "from pathlib import Path\ndef read_fixture(path): return Path(path).read_text()\n",
        )
        self.write(
            "server/tests/test_literal.py",
            'from tools.fixture_reader import read_fixture\nvalue = read_fixture("server/tests/fixtures/first.json")\n',
        )
        self.write(
            "server/tests/test_dynamic.py",
            "from tools.fixture_reader import read_fixture\ndef check(path): return read_fixture(path)\n",
        )
        self.write("server/tests/test_other.py", "import unittest\n")
        self.write("server/tests/fixtures/first.json", "{}")
        before = self.graph()
        self.write("server/tests/fixtures/first.json", '{"changed": true}')
        plan = select_changes(before, self.graph())
        self.assertEqual(
            plan["selected_module_names"], ["test_dynamic", "test_literal"]
        )
        self.assertTrue(
            any(
                row["reason"] == "unresolved-reader-argument"
                for row in plan["unknowns"]
            )
        )

    def test_method_and_reexported_reader_unknowns_do_not_disappear(self):
        self.write(
            "server/tools/reader.py",
            "from pathlib import Path\ndef read_fixture(path): return Path(path).read_text()\nclass Reader:\n def read_method(self, path): return Path(path).read_text()\n",
        )
        self.write(
            "server/tools/exported.py",
            "from tools.reader import read_fixture as exported_reader\n",
        )
        self.write(
            "server/tests/test_alias.py",
            'from tools.exported import exported_reader\nvalue = exported_reader("server/tests/fixtures/first.json")\n',
        )
        self.write(
            "server/tests/test_method.py",
            "from tools.reader import Reader\ndef run(reader, path): return reader.read_method(path)\n",
        )
        self.write("server/tests/test_other.py", "import unittest\n")
        self.write("server/tests/fixtures/first.json", "{}")
        before = self.graph()
        self.write("server/tests/fixtures/first.json", '{"changed": true}')
        plan = select_changes(before, self.graph())
        self.assertIn("test_alias", plan["selected_module_names"])
        self.assertIn("test_method", plan["selected_module_names"])
        self.assertNotIn("test_other", plan["selected_module_names"])
        self.assertTrue(
            any(
                row["reason"] == "unresolved-parameterized-reader-callers"
                for row in plan["unknowns"]
            )
        )

    def test_literal_dynamic_import_and_source_as_data_are_real_dependencies(self):
        self.write("server/wakfu_server/combat/primitive.py", "VALUE = 1\n")
        self.write(
            "server/tests/test_import.py",
            'import importlib\nvalue = importlib.import_module("wakfu_server.primitive")\n',
        )
        self.write(
            "server/tests/test_read.py",
            'from pathlib import Path\nSOURCE = Path(__file__).resolve().parents[1] / "wakfu_server" / "combat" / "primitive.py"\nvalue = SOURCE.read_text()\n',
        )
        before = self.graph()
        self.write("server/wakfu_server/combat/primitive.py", "VALUE = 2\n")
        plan = select_changes(before, self.graph())
        self.assertEqual(plan["selected_module_names"], ["test_import", "test_read"])

    def test_policy_identity_and_runner_policy_change_invalidate(self):
        self.write(
            "server/tests/test_policy.py",
            'import os\nvalue = os.environ.get("WAKFU_PUBLIC_DAMAGE_POLICY", "original")\n',
        )
        with patch.dict("os.environ", {"WAKFU_PUBLIC_DAMAGE_POLICY": "first"}):
            before = self.graph()
        with patch.dict("os.environ", {"WAKFU_PUBLIC_DAMAGE_POLICY": "second"}):
            after = self.graph()
        self.assertEqual(
            select_changes(before, after)["selected_module_names"], ["test_policy"]
        )
        after["provenance"]["runner_policy"]["module_timeout_seconds"] = 99
        after["sha256"] = canonical_digest(
            {k: v for k, v in after.items() if k != "sha256"}
        )
        self.assertTrue(
            any(
                row["reason"] == "runner-policy-changed"
                for row in select_changes(before, after)["fallbacks"]
            )
        )

    def test_keyword_readers_and_escaped_function_aliases_keep_input_dependencies(self):
        self.write(
            "server/tools/readers.py",
            "from pathlib import Path\ndef read_fixture(*, path): return Path(path).read_text()\n",
        )
        self.write(
            "server/tests/test_keyword.py",
            'from tools.readers import read_fixture\nvalue = read_fixture(path="server/tests/fixtures/first.json")\n',
        )
        self.write(
            "server/tests/test_escape.py",
            "from tools.readers import read_fixture\nreader = read_fixture\ndef run(path): return reader(path=path)\n",
        )
        self.write(
            "server/tests/test_native_alias.py",
            "from wakfu_server import native_catalog\nreader = native_catalog.read_bytes\ndef run(path): return reader(path)\n",
        )
        self.write(
            "server/wakfu_server/storage/native_catalog.py",
            "def read_bytes(path): pass\n",
        )
        self.write("server/tests/test_other.py", "import unittest\n")
        self.write("server/tests/fixtures/first.json", "{}")
        before = self.graph()
        self.write("server/tests/fixtures/first.json", '{"changed": true}')
        plan = select_changes(before, self.graph())
        for module in ("test_keyword", "test_escape", "test_native_alias"):
            self.assertIn(module, plan["selected_module_names"])
        self.assertNotIn("test_other", plan["selected_module_names"])
        self.assertTrue(
            any(
                row["reason"] == "escaped-parameterized-reader"
                for row in plan["unknowns"]
            )
        )

    def test_changed_unimported_provider_selects_unchanged_runtime_consumer(self):
        self.write(
            "server/wakfu_server/combat/combat_effect_runtime.py",
            "class NativeRuntimeContexts:\n damage: object\n",
        )
        self.write(
            "server/wakfu_server/combat/arbitrary_provider.py",
            "def damage(): return 1\n",
        )
        self.write(
            "server/tests/test_context_consumer.py",
            "from wakfu_server.combat_effect_runtime import NativeRuntimeContexts\n",
        )
        self.write("server/tests/test_other.py", "import unittest\n")
        before = self.graph()
        self.write(
            "server/wakfu_server/combat/arbitrary_provider.py",
            "def damage(): return 2\n",
        )
        plan = select_changes(before, self.graph())
        self.assertIn("test_context_consumer", plan["selected_module_names"])
        self.assertNotIn("test_other", plan["selected_module_names"])
        self.assertTrue(
            any(row["reason"] == "runtime-provider-binding" for row in plan["unknowns"])
        )

    def test_imported_environment_aliases_are_hashed_and_dynamic_names_unknown(self):
        self.write(
            "server/tests/test_policy.py",
            'from os import getenv as policy, environ as env\na = policy("WAKFU_PUBLIC_POLICY", "native")\nb = env.get("WAKFU_OTHER_POLICY", "native")\ndef query(name): return policy(name)\n',
        )
        with patch.dict("os.environ", {"WAKFU_PUBLIC_POLICY": "first"}):
            before = self.graph()
        with patch.dict("os.environ", {"WAKFU_PUBLIC_POLICY": "second"}):
            after = self.graph()
        self.assertTrue(
            any(
                row["id"] == "runtime-policy:WAKFU_OTHER_POLICY"
                for row in before["nodes"]
            )
        )
        plan = select_changes(before, after)
        self.assertIn("test_policy", plan["selected_module_names"])
        self.assertTrue(
            any(
                row["reason"] == "dynamic-runtime-policy-name"
                for row in plan["unknowns"]
            )
        )

    def test_present_private_policy_values_never_qualify_an_empty_selection(self):
        self.write(
            "server/tools/backend_reader.py",
            'import os\ndef backend(): return os.environ.get("WAKFU_DATABASE_URL")\n',
        )
        self.write(
            "server/tests/test_backend.py", "from tools.backend_reader import backend\n"
        )
        self.write("server/tests/test_other.py", "import unittest\n")
        first, second = (
            "postgresql://private-first.example/secret",
            "postgresql://private-second.example/secret",
        )
        with patch.dict("os.environ", {"WAKFU_DATABASE_URL": first}):
            before = self.graph()
        with patch.dict("os.environ", {"WAKFU_DATABASE_URL": second}):
            after = self.graph()
        plan = select_changes(before, after)
        self.assertEqual(plan["changed_node_ids"], [])
        self.assertEqual(plan["selected_module_names"], ["test_backend"])
        self.assertTrue(
            any(
                row["reason"] == "private-environment-input-not-content-bound"
                for row in plan["unknowns"]
            )
        )
        raw = json.dumps({"graph": after, "plan": plan})
        import hashlib

        for secret in (first, second):
            self.assertNotIn(secret, raw)
            self.assertNotIn(hashlib.sha256(secret.encode()).hexdigest(), raw)

    def test_runtime_policy_attestation_binds_public_values_and_private_presence_only(
        self,
    ):
        names = ["WAKFU_PUBLIC_POLICY", "WAKFU_DATABASE_URL"]
        with patch.dict(
            "os.environ",
            {"WAKFU_PUBLIC_POLICY": "first", "WAKFU_DATABASE_URL": "private-a"},
        ):
            first = runtime_policy_inputs(names)
        with patch.dict(
            "os.environ",
            {"WAKFU_PUBLIC_POLICY": "first", "WAKFU_DATABASE_URL": "private-b"},
        ):
            private_changed = runtime_policy_inputs(names)
        self.assertEqual(first, private_changed)
        with patch.dict(
            "os.environ",
            {"WAKFU_PUBLIC_POLICY": "second", "WAKFU_DATABASE_URL": "private-b"},
        ):
            public_changed = runtime_policy_inputs(names)
        self.assertNotEqual(
            first["runtime_policy_sha256"], public_changed["runtime_policy_sha256"]
        )
        with self.assertRaises(ValueError):
            runtime_policy_inputs(["../unsafe"])

    def test_shadow_rejects_policy_attestation_drift_and_missing_tracked_names(self):
        self.write(
            "server/tests/test_policy.py",
            'import os\nvalue = os.getenv("WAKFU_PUBLIC_POLICY")\n',
        )
        graph = self.graph()
        plan = select_changes(None, graph)
        report = self.full_report(graph)
        report["impact_inputs_after"]["runtime_policy_sha256"] = "z" * 64
        self.assertEqual(compare_shadow(plan, report)["status"], "incompatible")
        report = self.full_report(graph)
        report["impact_inputs_after"].pop("runtime_policy_names")
        self.assertNotEqual(compare_shadow(plan, report)["status"], "matched")

    def test_cli_capture_explain_are_private_exclusive_and_never_query_catalog(self):
        self.write("server/tests/test_one.py", "import unittest\n")
        catalog_path = self.root / "catalog-input.json"
        catalog_path.write_text(json.dumps(self.catalog))
        before = self.root / "before.json"
        after = self.root / "after.json"
        plan = self.root / "plan.json"
        with patch(
            "tools.combat_baseline_inventory.catalog_manifest",
            side_effect=AssertionError("No SQL metadata reads"),
        ):
            self.assertEqual(
                main(
                    [
                        "capture",
                        "--root",
                        str(self.root),
                        "--catalog-inventory",
                        str(catalog_path),
                        "--output",
                        str(before),
                    ]
                ),
                0,
            )
            self.write("server/tests/test_one.py", "import unittest\n# change\n")
            self.assertEqual(
                main(
                    [
                        "capture",
                        "--root",
                        str(self.root),
                        "--catalog-inventory",
                        str(catalog_path),
                        "--output",
                        str(after),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "explain",
                        "--before",
                        str(before),
                        "--after",
                        str(after),
                        "--output",
                        str(plan),
                    ]
                ),
                0,
            )
        self.assertEqual(
            json.loads(plan.read_text())["selected_module_names"], ["test_one"]
        )
        self.assertEqual(plan.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(SystemExit) as raised:
            main(["explain", "--after", str(after), "--output", str(plan)])
        self.assertEqual(raised.exception.code, 2)

    def test_tampered_graph_rejected(self):
        graph = self.graph()
        graph["module_names"].append("invented")
        with self.assertRaises(ValueError):
            select_changes(None, graph)


class ActualRepositoryImpactWitnessTests(unittest.TestCase):
    """Actual source reachability probes, not catalog publication assertions."""

    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        # Supplied identity is a fixture for structural selection only. These
        # probes never qualify a real publication or execute native gameplay.
        catalog = {
            "status": "published",
            "revision": "static-graph-fixture",
            "documents": {},
            "sha256": "a" * 64,
            "publication_verified": True,
        }
        cls.graph = build_graph(root, catalog_inventory=catalog)

    def plan_for(self, identity):
        after = copy.deepcopy(self.graph)
        row = next(row for row in after["nodes"] if row["id"] == identity)
        row["sha256"] = "f" * 64
        after["provenance"]["source_manifest_sha256"] = "b" * 64
        after["sha256"] = canonical_digest(
            {k: v for k, v in after.items() if k != "sha256"}
        )
        return select_changes(self.graph, after)

    def test_source_extraction_merge_consumer_and_native_oracle_are_selected(self):
        plan = self.plan_for("module:server/wakfu_server/combat/combat_npc_attack.py")
        self.assertIn("test_monster_spell_activation", plan["selected_module_names"])
        oracle = self.plan_for(
            "input:server/tests/fixtures/native_state_cleanup_982.json"
        )
        self.assertIn("test_combat_state_cleanup", oracle["selected_module_names"])
        self.assertLess(
            len(oracle["selected_module_names"]), len(oracle["discovered_module_names"])
        )

    def test_real_native_action_contract_is_exposed(self):
        plan = self.plan_for(
            "module:server/wakfu_server/combat/combat_native_action_ids.py"
        )
        self.assertIn("test_combat_native_action_ids", plan["selected_module_names"])
        witness = next(
            row
            for row in self.graph["nodes"]
            if row["id"]
            == "method:server/tests/test_combat_native_action_ids.py:NativeActionIdTests.test_unique_actions_preserve_payload_identity_and_turn_ack"
        )
        self.assertEqual(witness["kind"], "test-method")

    def test_local_game_source_as_data_selects_placement_deadline(self):
        plan = self.plan_for("module:server/local_game_server.py")
        self.assertIn("test_placement_deadline", plan["selected_module_names"])

    def test_real_multihop_inheritance_preserves_postgres_fixture_dependency(self):
        plan = self.plan_for("module:server/tests/postgres_case.py")
        for module in (
            "test_combat_heroes_postgres",
            "test_combat_hero_takeover_postgres",
            "test_combat_hero_shared_abort_postgres",
        ):
            self.assertIn(module, plan["selected_module_names"])
        self.assertTrue(
            any(
                row["kind"] == "inherits"
                and row["consumer"].endswith(":HeroSharedAbortPostgresTests")
                for row in self.graph["edges"]
            )
        )


if __name__ == "__main__":
    unittest.main()
