"""Source-bound singleton fixture and exact future execution-context gates."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import os
import sys
from unittest.mock import patch
from tools import combat_test_impact as impact


class IsolatedReaderImpactTests(unittest.TestCase):
    def proof(self, root, bad=None):
        def write(name, value):
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(value if isinstance(value, str) else json.dumps(value))
            return p

        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        fixture = "server/tests/test_fixture.py"
        api = "server/wakfu_server/storage/native_catalog.py"
        write(fixture, "class Fixture:\n def test_case(self): pass\n")
        write(api, 'def read_published_bytes(name): return b"fixture"\n')
        runner = write(
            ".runtime/proof/runner.py", "# synthetic evidence fixture; never executed\n"
        )
        ids = ["test_fixture.Fixture.test_case"]
        flags = dict(isolated=True, no_site=True, ignore_environment=True)
        catalog = dict(revision="fixture", sha256="c" * 64, publication_verified=True)
        child = dict(
            test_outcomes=[dict(test_id=ids[0], status="passed")],
            exact_test_ids_preflight=ids,
            result=dict(tests_run=1, failures=0, errors=0, skips=0, successful=True),
            python_flags=flags,
            effective_environment_digest_before="e" * 64,
            effective_environment_digest_after="e" * 64,
            catalog=dict(
                revision="fixture", catalog_sha256="c" * 64, publication_verified=True
            ),
            import_origins=dict(test_fixture=fixture, native_catalog=api),
        )
        env = dict(
            python_flags=flags,
            sha256_sorted_key_value_pairs="e" * 64,
            actual_test_ids=ids,
            discovered_affected_modules=[],
            runner_sha256=sha(runner),
            bootstrap_sha256="a" * 64,
        )
        if bad == "foreign-test":
            child["test_outcomes"].append(
                dict(test_id="test_other.Other.test_case", status="passed")
            )
        if bad == "changed-environment":
            child["effective_environment_digest_after"] = "f" * 64
        if bad == "startup-flags":
            child["python_flags"] = {**flags, "isolated": False}
        child_path = write(".runtime/proof/child-results.json", child)
        fixture_sha = sha(root / fixture)
        parent = dict(
            return_code=0,
            source_stable=True,
            exact_test_ids=ids,
            child_results_sha256=sha(child_path),
            actual_source_sha256_before={fixture: fixture_sha},
            source_sha256_after={fixture: fixture_sha},
            command=["python", "-I", "-S", str(runner)],
            child_results=str(child_path),
            environment_digest_sidecar=str(
                root / ".runtime/proof/effective-environment.json"
            ),
        )
        if bad == "nonterminal":
            parent["return_code"] = None
        parent_path = write(".runtime/proof/receipt.json", parent)
        env_path = write(".runtime/proof/effective-environment.json", env)
        preflight = write(
            ".runtime/proof/preflight.json",
            {
                k: parent[k]
                for k in ("command", "exact_test_ids", "actual_source_sha256_before")
            },
        )
        seal = write(
            ".runtime/proof/seal.json",
            {"files": {api: {"after_sha256": sha(root / api)}}},
        )
        declaration = dict(
            status="qualified-source-bound-isolated-fixture",
            fixture_source_path=fixture,
            fixture_source_sha256=fixture_sha,
            reader_sources={api: sha(root / api)},
            terminal_authority=dict(
                artifacts={
                    p.name: dict(path=p.relative_to(root).as_posix(), sha256=sha(p))
                    for p in (parent_path, child_path, env_path, preflight)
                },
                runner_path=runner.relative_to(root).as_posix(),
                runner_sha256=sha(runner),
                api_source_seal_path=seal.relative_to(root).as_posix(),
                api_source_seal_sha256=sha(seal),
            ),
        )
        files = {fixture: fixture_sha, api: sha(root / api)}
        if bad == "stale-source":
            files[fixture] = "0" * 64
        return declaration, files, catalog

    def test_singleton_proof_rejects_stale_foreign_unfinished_or_changed_inputs(self):
        for bad in (
            None,
            "stale-source",
            "foreign-test",
            "nonterminal",
            "changed-environment",
            "startup-flags",
        ):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                declaration, files, catalog = self.proof(root, bad)
                qualified, errors = impact._qualified_isolated_reader_fixtures(
                    root,
                    [declaration],
                    files,
                    {"native_catalog.read_published_bytes"},
                    catalog,
                )
                if bad is None:
                    self.assertEqual(set(qualified), {"server/tests/test_fixture.py"})
                    self.assertEqual(errors, [])
                    self.assertFalse(
                        qualified["server/tests/test_fixture.py"]["data_qualified"]
                    )
                else:
                    self.assertEqual(qualified, {})
                    self.assertTrue(errors)

    def test_context_scope_requires_exact_future_environment_and_fixture_isolation(
        self,
    ):
        context = dict(
            effective_environment_sha256=hashlib.sha256(
                json.dumps(
                    sorted(os.environ.items()),
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
            ).hexdigest(),
            interpreter_sha256=hashlib.sha256(
                Path(sys.executable).read_bytes()
            ).hexdigest(),
            startup_flags=dict(
                isolated=bool(sys.flags.isolated),
                no_site=bool(sys.flags.no_site),
                ignore_environment=bool(sys.flags.ignore_environment),
            ),
            catalog_revision="fixture",
            catalog_inventory_sha256="c" * 64,
            future_runner_must_match_before_imports=True,
        )
        fixture = "server/tests/test_fixture.py"
        graph = dict(
            schema=impact.SCHEMA,
            builder="fixed",
            operation_registry={},
            provenance=dict(
                catalog_inventory_sha256="c" * 64,
                catalog_publication_verified=True,
                runner_policy={},
                environment_sha256="p" * 64,
                required_observed_execution_context=context,
            ),
            nodes=[
                dict(
                    id="module:" + fixture,
                    kind="module",
                    path=fixture,
                    category="test",
                    sha256="x",
                ),
                dict(
                    id="test-module:" + fixture,
                    kind="test-module",
                    path=fixture,
                    module_name="test_fixture",
                ),
                dict(
                    id="module:server/tests/test_leaf.py",
                    kind="module",
                    path="server/tests/test_leaf.py",
                    category="test",
                    sha256="old",
                ),
                dict(
                    id="test-module:server/tests/test_leaf.py",
                    kind="test-module",
                    path="server/tests/test_leaf.py",
                    module_name="test_leaf",
                ),
            ],
            edges=[
                dict(
                    consumer="test-module:" + fixture,
                    dependency="module:" + fixture,
                    kind="import",
                ),
                dict(
                    consumer="test-module:server/tests/test_leaf.py",
                    dependency="module:server/tests/test_leaf.py",
                    kind="import",
                ),
            ],
            unknowns=[
                dict(
                    owner="module:" + fixture,
                    reason="unqualified-published-reader",
                    domain="source-unbounded",
                    fallback="owner-consumers",
                )
            ],
            global_invalidation=[],
            module_names=["test_fixture", "test_leaf"],
            isolated_reader_fixture_registry=dict(
                qualified={
                    fixture: dict(
                        required_execution_model="singleton-test-module-subprocess"
                    )
                }
            ),
        )
        graph["sha256"] = impact.canonical_digest(graph)
        self.assertEqual(
            impact.select_changes(graph, graph)["selected_module_names"], []
        )
        after = copy.deepcopy(graph)
        after["nodes"][2]["sha256"] = "new"
        after.pop("sha256")
        after["sha256"] = impact.canonical_digest(after)
        plan = impact.select_changes(graph, after)
        self.assertEqual(plan["selected_module_names"], ["test_fixture", "test_leaf"])
        self.assertTrue(
            any(
                row["reason"] == "unqualified-published-reader"
                for row in plan["unknowns"]
            )
        )
        catalog = dict(publication_verified=True, revision="fixture", sha256="c" * 64)
        self.assertEqual(
            impact.verify_required_execution_context(
                plan, actual_catalog=catalog, enforced_singleton_fixture_paths=[fixture]
            )["status"],
            "actual-context-matched-before-imports",
        )
        with patch.dict(
            os.environ, {"UNPLANNED_CONTEXT_CHANGE": "1"}
        ), self.assertRaises(ValueError):
            impact.verify_required_execution_context(
                plan, actual_catalog=catalog, enforced_singleton_fixture_paths=[fixture]
            )
        with self.assertRaises(ValueError):
            impact.verify_required_execution_context(
                plan, actual_catalog=catalog, enforced_singleton_fixture_paths=[]
            )
        no_context = {**plan, "required_observed_execution_context": None}
        with self.assertRaises(ValueError):
            impact.verify_required_execution_context(
                no_context, actual_catalog=catalog, enforced_singleton_fixture_paths=[]
            )
        self.assertEqual(
            impact.verify_required_execution_context(
                no_context,
                actual_catalog=catalog,
                enforced_singleton_fixture_paths=[fixture],
            )["required_fixture_paths"],
            [fixture],
        )
        after["unknowns"][0]["fallback"] = "full"
        after.pop("sha256")
        after["sha256"] = impact.canonical_digest(after)
        self.assertTrue(
            any(
                row["scope"] == "full"
                for row in impact.select_changes(graph, after)["fallbacks"]
            )
        )
