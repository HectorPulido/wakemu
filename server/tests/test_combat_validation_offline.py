"""Audited offline qualifications preserve hits only within their real closure."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools import combat_validation_offline as offline


ROOT = Path(__file__).resolve().parents[2]
SHA = hashlib.sha256(b"runner and environment fixture").hexdigest()
OTHER = hashlib.sha256(b"changed environment").hexdigest()
MODULE = "test_combat_transaction_rng"


class OfflineQualificationTests(unittest.TestCase):
    @contextmanager
    def checkout(self):
        registry = json.loads((ROOT / offline.REGISTRY).read_bytes())
        entry = registry["modules"][MODULE]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (*entry["source"], *offline.IMPLEMENTATIONS, offline.REGISTRY):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            yield root

    def candidate(self, root, **changes):
        args = dict(
            runner_sha256=SHA,
            environment_sha256=SHA,
            policies={
                "module_timeout_seconds": 10,
                "python_import_mode": "isolated-no-site-v1",
                "python_startup": dict(offline.PYTHON_STARTUP),
            },
        )
        args.update(changes)
        return offline.qualified_manifest(root, MODULE, **args)

    def edit_registry(self, root, change):
        path = root / offline.REGISTRY
        registry = json.loads(path.read_bytes())
        change(registry["modules"][MODULE])
        path.write_text(json.dumps(registry))

    def test_actual_rng_module_has_complete_reviewed_four_file_qualification(self):
        candidate = self.candidate(ROOT)
        self.assertIsNotNone(candidate)
        document = candidate.as_dict()
        registry = json.loads((ROOT / offline.REGISTRY).read_bytes())
        entry = registry["modules"][MODULE]
        self.assertEqual(document["test_ids"], entry["test_ids"])
        self.assertEqual(len(document["test_ids"]), 3)
        self.assertEqual(len(entry["source"]), 4)
        self.assertEqual(document["rng"]["seeds"], [9])
        self.assertFalse(document["rng"]["uncontrolled_consumed_entropy"])
        self.assertEqual(document["catalog"], {})
        self.assertEqual(
            document["policies"]["import_origins"]["wakfu_server"],
            "server/wakfu_server/__init__.py",
        )

    def test_unrelated_edit_preserves_key_and_reviewed_edit_requires_fresh(self):
        with self.checkout() as root:
            first = self.candidate(root)
            (root / "server/unrelated.py").write_text("irrelevant = True\n")
            self.assertEqual(first.key, self.candidate(root).key)
            dependency = (
                root / "server/wakfu_server/combat/combat_random_transaction.py"
            )
            dependency.write_bytes(
                dependency.read_bytes() + b"\n# changed dependency\n"
            )
            self.assertIsNone(self.candidate(root))

    def test_runtime_policy_environment_runner_and_declaration_changes_invalidate_key(
        self,
    ):
        with self.checkout() as root:
            original = self.candidate(root)
            for change in (
                dict(environment_sha256=OTHER),
                dict(runner_sha256=OTHER),
                dict(
                    policies={
                        "module_timeout_seconds": 20,
                        "python_import_mode": "isolated-no-site-v1",
                        "python_startup": dict(offline.PYTHON_STARTUP),
                    }
                ),
            ):
                with self.subTest(change=change):
                    self.assertNotEqual(
                        original.key, self.candidate(root, **change).key
                    )
            path = root / offline.REGISTRY
            path.write_bytes(path.read_bytes() + b"\n")
            self.assertNotEqual(original.key, self.candidate(root).key)

    def test_reviewed_oracle_fixture_and_catalog_declarations_bind_bytes(self):
        with self.checkout() as root:
            previous = self.candidate(root)
            path = root / "proof.json"
            path.write_bytes(b'{"native":true}')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.edit_registry(
                root, lambda entry: entry["oracles"].update({"proof.json": digest})
            )
            with_oracle = self.candidate(root)
            self.assertNotEqual(previous.key, with_oracle.key)
            fixture = root / "fixture.json"
            fixture.write_bytes(b"[]")
            fixture_digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
            self.edit_registry(
                root,
                lambda entry: entry["fixtures"].update(
                    {"fixture.json": fixture_digest}
                ),
            )
            self.assertNotEqual(with_oracle.key, self.candidate(root).key)
            catalog = root / "catalog.json"
            catalog.write_bytes(b'{"revision":"fixture-v1"}')
            catalog_digest = hashlib.sha256(catalog.read_bytes()).hexdigest()
            before_catalog = self.candidate(root)
            self.edit_registry(
                root,
                lambda entry: entry["catalog"].update({"catalog.json": catalog_digest}),
            )
            declared = self.candidate(root)
            self.assertNotEqual(before_catalog.key, declared.key)
            for dependency in (path, fixture, catalog):
                with self.subTest(dependency=dependency.name):
                    original = dependency.read_bytes()
                    dependency.write_bytes(b"tampered")
                    self.assertIsNone(self.candidate(root))
                    dependency.write_bytes(original)
                    self.assertEqual(self.candidate(root).key, declared.key)

    def test_added_import_shadows_make_prior_key_ineligible_before_lookup(self):
        shadows = (
            "server/tests/random.py",
            "server/types.py",
            "server/tools/functools.py",
            "pathlib.py",
            "server/tests/wakfu_server/__init__.py",
            "server/wakfu_server/combat_transaction_rng.py",
            "server/tests/test_combat_transaction_rng/__init__.py",
        )
        for name in shadows:
            with self.subTest(shadow=name), self.checkout() as root:
                self.assertIsNotNone(self.candidate(root))
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("raise AssertionError('must never be imported')\n")
                self.assertIsNone(self.candidate(root))

    def test_missing_symlink_and_unsafe_inputs_never_qualify(self):
        for damage in ("missing", "symlink", "unsafe"):
            with self.subTest(damage=damage), self.checkout() as root:
                path = root / "server/tests/test_combat_transaction_rng.py"
                if damage == "missing":
                    path.unlink()
                elif damage == "symlink":
                    original = path.read_bytes()
                    path.unlink()
                    (root / "elsewhere.py").write_bytes(original)
                    path.symlink_to(root / "elsewhere.py")
                else:
                    self.edit_registry(
                        root,
                        lambda entry: entry["source"].update({"../escape.py": SHA}),
                    )
                self.assertIsNone(self.candidate(root))

    def test_unknown_or_invalid_registry_yields_fresh_diagnostics_without_imports(self):
        with self.checkout() as root:
            self.assertIsNone(
                offline.qualified_manifest(
                    root,
                    "test_unknown",
                    runner_sha256=SHA,
                    environment_sha256=SHA,
                    policies={},
                )
            )
            (root / offline.REGISTRY).write_text("{invalid")
            result = offline.eligibility(
                root, MODULE, runner_sha256=SHA, environment_sha256=SHA, policies={}
            )
            self.assertIsNone(result.manifest)
            self.assertIn("unavailable", result.reason)

    def test_qualification_implementation_and_store_implementation_are_inputs(self):
        with self.checkout() as root:
            first = self.candidate(root)
            for name in offline.IMPLEMENTATIONS:
                path = root / name
                path.write_bytes(path.read_bytes() + b"\n# verifier revision\n")
                updated = self.candidate(root)
                self.assertNotEqual(first.key, updated.key)
                first = updated

    def test_qualified_recipe_requires_explicit_isolated_no_site_startup_contract(self):
        with self.checkout() as root:
            for policies in (
                {},
                {"python_import_mode": "ordinary"},
                {"python_import_mode": "isolated-no-site-v1", "python_startup": {}},
                {
                    "python_import_mode": "isolated-no-site-v1",
                    "python_startup": {**offline.PYTHON_STARTUP, "no_site": False},
                },
                {
                    "python_import_mode": "isolated-no-site-v1",
                    "python_startup": {**offline.PYTHON_STARTUP, "isolated": 1},
                },
            ):
                with self.subTest(policies=policies):
                    self.assertIsNone(self.candidate(root, policies=policies))
