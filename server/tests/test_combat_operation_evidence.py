"""Evidence joins preserve scope, invalidation and all shared consumers.

Terminal reports in these unit tests are synthetic verifier fixtures. They are
never exported as real execution evidence or native-operation accreditation.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.combat_operation_catalog import compile_catalog
from tools.combat_operation_evidence import REGISTRY_SOURCE, build_operation_evidence
from tools import combat_validation_offline as offline
from tools import combat_validation_reuse as reuse


ROOT = Path(__file__).resolve().parents[2]
SHA = hashlib.sha256(b"synthetic unit verifier inputs").hexdigest()
MODULE = "test_combat_displacement_geometry"
POLICIES = dict(
    python_import_mode="isolated-no-site-v1",
    python_startup=dict(offline.PYTHON_STARTUP),
    module_timeout_seconds=30,
)


def compiled():
    return compile_catalog(
        {
            "spells": {"10": [100], "11": [101], "12": [102]},
            "effects": {
                "100": {"effect_class": 300, "parameters": [1, 0]},
                "101": {"effect_class": 300, "parameters": [1, 0]},
                "102": {"effect_class": 803},
            },
        },
        [("spell", 10), ("spell", 11), ("spell", 12)],
    )


class OperationEvidenceTests(unittest.TestCase):
    @contextmanager
    def checkout(self):
        registry = json.loads((ROOT / offline.REGISTRY).read_bytes())
        entry = registry["modules"][MODULE]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            metadata = compiled().report().get("registry_sources", {})
            for name in (
                *entry["source"],
                *offline.IMPLEMENTATIONS,
                offline.REGISTRY,
                REGISTRY_SOURCE,
                *metadata,
            ):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            store = reuse.LocalResultStore(Path(directory) / "store")
            yield root, store

    def explain(self, root=ROOT, store=None, **changes):
        return build_operation_evidence(
            compiled(),
            root=root,
            store=store,
            runner_sha256=SHA,
            environment_sha256=SHA,
            policies=POLICIES,
            **changes
        )

    def publish_synthetic_fixture(self, root, store):
        manifest = offline.qualified_manifest(
            root, MODULE, runner_sha256=SHA, environment_sha256=SHA, policies=POLICIES
        )
        self.assertIsNotNone(manifest)
        document = manifest.as_dict()
        ids = document["test_ids"]
        report = dict(
            discovery=dict(
                module_names=[MODULE], tests=len(ids), test_ids=ids, loader_errors=[]
            ),
            result=dict(
                tests_run=len(ids),
                failures=0,
                errors=0,
                skipped=0,
                expected_failures=0,
                unexpected_successes=0,
                successful=True,
            ),
            test_outcomes=[dict(test_id=name, status="passed") for name in ids],
            failures=[],
            errors=[],
            skipped=[],
            import_origins=document["policies"]["import_origins"],
            python_startup=offline.PYTHON_STARTUP,
        )
        parent = reuse.ParentObservation(
            status="completed",
            return_code=0,
            normal_exit=True,
            invocation_id="synthetic-unit-fixture",
            invoked_module=MODULE,
            scope=document["scope"],
            runner_sha256=SHA,
        )
        raw = reuse.canonical_bytes(report)
        store.publish(reuse.terminal_receipt(manifest, manifest, parent, raw), raw)
        return manifest

    def test_missing_shared_family_reports_all_consumers_without_operation_claim(self):
        report = self.explain()
        missing = report["missing_operations"]
        self.assertEqual(
            missing,
            [
                {
                    "family": 803,
                    "path": ["spell:12", "effect:102"],
                    "paths": [["spell:12", "effect:102"]],
                    "affected_consumers": [{"kind": "spell", "reference": 12}],
                }
            ],
        )
        operation = report["operations"]["spatial.displacement"]
        self.assertEqual([row["reference"] for row in operation["consumers"]], [10, 11])
        self.assertEqual(operation["operation_support"], "conditional")
        self.assertEqual(operation["combination_verification"], "unknown")
        self.assertEqual(operation["modeled_client_compatibility"], "unknown")

    def test_reuse_is_partial_and_preserves_terminal_identity(self):
        with self.checkout() as (root, store):
            manifest = self.publish_synthetic_fixture(root, store)
            report = self.explain(root, store)
            geometry = report["module_evidence"][MODULE]
            self.assertEqual(geometry["status"], "reused")
            self.assertEqual(geometry["key"], manifest.key)
            self.assertEqual(geometry["invocation_id"], "synthetic-unit-fixture")
            self.assertEqual(geometry["origin"], "executed")
            operation = report["operations"]["spatial.displacement"]
            self.assertEqual(operation["reused_partial_scopes"], [MODULE])
            self.assertEqual(operation["operation_support"], "conditional")
            self.assertEqual(report["combination_verification"], "unknown")

    def test_unrelated_edit_reuses_but_relevant_edit_invalidates_and_selects_consumers(
        self,
    ):
        with self.checkout() as (root, store):
            self.publish_synthetic_fixture(root, store)
            original = self.explain(root, store)
            (root / "unrelated.py").write_text("irrelevant = True\n")
            unchanged = self.explain(root, store)
            self.assertEqual(
                original["module_evidence"][MODULE],
                unchanged["module_evidence"][MODULE],
            )
            path = "server/wakfu_server/combat/combat_displacement_geometry.py"
            dependency = root / path
            dependency.write_bytes(
                dependency.read_bytes() + b"\n# changed unit fixture\n"
            )
            changed = self.explain(root, store, changed_paths=[path])
            self.assertEqual(
                changed["module_evidence"][MODULE]["status"], "fresh-required"
            )
            self.assertIn(
                "Reviewed dependency changed",
                changed["module_evidence"][MODULE]["reason"],
            )
            self.assertEqual(
                changed["impact"]["affected_operations"], ["spatial.displacement"]
            )
            self.assertEqual(
                [row["reference"] for row in changed["impact"]["affected_consumers"]],
                [10, 11],
            )
            self.assertFalse(changed["impact"]["broader_inspection_required"])
            self.assertIn(MODULE, changed["impact"]["relevant_tests"])

    def test_contract_change_requires_relevant_tests_but_does_not_discard_partial_scope(
        self,
    ):
        with self.checkout() as (root, store):
            self.publish_synthetic_fixture(root, store)
            report = self.explain(
                root, store, changed_operations=["spatial.displacement"]
            )
            self.assertEqual(report["module_evidence"][MODULE]["status"], "reused")
            self.assertIn(MODULE, report["impact"]["relevant_tests"])
            self.assertEqual(report["impact"]["mode"], "explanation-only")

    def test_unknown_inputs_require_broader_inspection(self):
        report = self.explain(
            changed_paths=["server/unknown.py"], changed_operations=["not.registered"]
        )
        self.assertTrue(report["impact"]["broader_inspection_required"])
        self.assertEqual(report["impact"]["unknown_paths"], ["server/unknown.py"])
        self.assertEqual(report["impact"]["unknown_operations"], ["not.registered"])

    def test_tampered_terminal_evidence_never_promotes_partial_scope(self):
        with self.checkout() as (root, store):
            manifest = self.publish_synthetic_fixture(root, store)
            (store.root / manifest.key / "report.json").write_bytes(b"{}")
            report = self.explain(root, store)
            self.assertEqual(
                report["module_evidence"][MODULE]["status"], "invalid-evidence"
            )
            self.assertEqual(
                report["operations"]["spatial.displacement"]["reused_partial_scopes"],
                [],
            )

    def test_mismatched_snapshot_registry_is_rejected_before_proof_lookup(self):
        with self.checkout() as (root, store):
            registry = root / REGISTRY_SOURCE
            registry.write_bytes(registry.read_bytes() + b"\n# stale snapshot\n")
            with self.assertRaisesRegex(ValueError, "differs from imported"):
                self.explain(root, store)

    def test_stale_compiled_contract_hash_is_rejected(self):
        report = compiled().report()
        report["nodes"]["effect:100"]["contract_sha256"] = SHA
        bindings = report["nodes"]["effect:100"].get("operation_contracts", {})
        if "spatial.displacement" in bindings:
            bindings["spatial.displacement"]["contract_sha256"] = SHA
        with self.assertRaisesRegex(ValueError, "contract identity is stale"):
            build_operation_evidence(
                report,
                root=ROOT,
                runner_sha256=SHA,
                environment_sha256=SHA,
                policies=POLICIES,
            )

    def test_described_operation_never_upgrades_unsupported_native_variant(self):
        plan = compile_catalog(
            {
                "spells": {"10": [100]},
                "effects": {"100": {"effect_class": 20, "parameters": [1, 0]}},
            },
            [("spell", 10)],
        )
        report = build_operation_evidence(
            plan,
            root=ROOT,
            runner_sha256=SHA,
            environment_sha256=SHA,
            policies=POLICIES,
        )
        operation = report["operations"]["resource.maximum"]
        self.assertEqual(operation["operation_support"], "unsupported")
        self.assertEqual(operation["node_support"], {"effect:100": "unsupported"})
        self.assertEqual(operation["modeled_client_compatibility"], "unknown")


if __name__ == "__main__":
    unittest.main()
