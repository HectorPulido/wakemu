"""Terminal evidence and compatible offline closures control result reuse."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import combat_validation_reuse as reuse


SHA = hashlib.sha256(b"audited-test-input").hexdigest()
OTHER = hashlib.sha256(b"changed").hexdigest()
IDS = ["test_example.Example.test_b", "test_example.Example.test_a"]


def manifest(**changes):
    values = dict(
        scope="explicit-offline-example",
        module="test_example",
        test_ids=IDS,
        source={"server/tests/test_example.py": SHA, "server/helper.py": SHA},
        fixtures={"fixtures/native.json": SHA},
        catalog={"native.json": SHA},
        oracles={"proof/native.json": SHA},
        declaration=SHA,
        runner=SHA,
        environment=SHA,
        policies={"mode": "native"},
        rng={"seed": 9},
    )
    values.update(changes)
    proof = dict(
        kind="audited-offline-closure-v1",
        complete=True,
        deterministic=True,
        external_state="none",
        closure_sha256=reuse.qualification_binding(
            {
                **values,
                "schema": reuse.SCHEMA,
                "test_ids": list(values["test_ids"]),
            }
        ),
    )
    return reuse.build_manifest(**values, qualification=proof)


def report():
    return dict(
        discovery=dict(
            module_names=["test_example"], tests=2, test_ids=IDS, loader_errors=[]
        ),
        result=dict(
            tests_run=2,
            failures=0,
            errors=0,
            skipped=0,
            expected_failures=0,
            unexpected_successes=0,
            successful=True,
        ),
        test_outcomes=[dict(test_id=name, status="passed") for name in IDS],
        failures=[],
        errors=[],
        skipped=[],
    )


def observation():
    return reuse.ParentObservation(
        status="completed",
        return_code=0,
        normal_exit=True,
        invocation_id="parent-run-1",
        invoked_module="test_example",
        scope="explicit-offline-example",
        runner_sha256=SHA,
    )


def receipt(candidate=None, child=None, parent=None, after=None):
    candidate = candidate or manifest()
    raw = json.dumps(child if child is not None else report()).encode()
    result = reuse.terminal_receipt(
        candidate, after or candidate, parent or observation(), raw
    )
    return result, raw


class ValidationReuseTests(unittest.TestCase):
    def test_manifest_is_immutable_and_preserves_order(self):
        candidate = manifest()
        detached = candidate.as_dict()
        detached["source"]["server/helper.py"] = OTHER
        self.assertEqual(candidate.as_dict()["source"]["server/helper.py"], SHA)
        self.assertEqual(candidate.as_dict()["test_ids"], IDS)
        self.assertNotEqual(candidate.key, manifest(test_ids=list(reversed(IDS))).key)
        with self.assertRaises(reuse.ReuseIneligible):
            manifest(test_ids=[IDS[0], IDS[0]])

    def test_unknown_incomplete_or_unbound_qualification_never_reuses(self):
        candidate = manifest().as_dict()
        for change in (
            dict(complete=False),
            dict(deterministic=False),
            dict(kind="static-import-guess"),
            dict(external_state="database"),
            dict(closure_sha256=OTHER),
        ):
            with self.subTest(change=change), self.assertRaises(reuse.ReuseIneligible):
                altered = copy.deepcopy(candidate)
                altered["qualification"].update(change)
                reuse.ValidationManifest(reuse.canonical_bytes(altered))
        with self.assertRaises(reuse.ReuseIneligible):
            manifest(source={"server/test.py": "invalid"})
        altered = copy.deepcopy(candidate)
        altered["source"]["server/helper.py"] = OTHER
        with self.assertRaises(reuse.ReuseIneligible):
            reuse.ValidationManifest(reuse.canonical_bytes(altered))
        for field, changed in (
            ("rng", {"seed": 10}),
            ("policies", {"mode": "changed"}),
            ("environment", OTHER),
        ):
            altered = copy.deepcopy(candidate)
            altered[field] = changed
            with self.subTest(stale_proof=field), self.assertRaises(
                reuse.ReuseIneligible
            ):
                reuse.ValidationManifest(reuse.canonical_bytes(altered))

    def test_closure_edits_bind_all_relevant_inputs_and_ignore_unrelated_files(self):
        original = manifest()
        changes = dict(
            source={"server/helper.py": OTHER},
            fixtures={"fixtures/native.json": OTHER},
            catalog={"native.json": OTHER},
            oracles={"proof/native.json": OTHER},
            declaration=OTHER,
            runner=OTHER,
            environment=OTHER,
            policies={"mode": "changed"},
            rng={"seed": 10},
        )
        for field, value in changes.items():
            with self.subTest(field=field):
                self.assertNotEqual(original.key, manifest(**{field: value}).key)
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "unrelated.py"
            outside.write_text("first")
            first = manifest().key
            outside.write_text("unrelated edit")
            self.assertEqual(first, manifest().key)

    def test_parent_terminal_exit_required_even_with_successful_json(self):
        for change in (
            dict(status="timeout", return_code=None, normal_exit=False),
            dict(return_code=1),
            dict(return_code=-9, normal_exit=False),
            dict(status="runner_error"),
            dict(normal_exit=False),
            dict(return_code=False),
            dict(invocation_id=""),
            dict(invocation_id="x" * 129),
            dict(invocation_id="unsafe/id"),
            dict(invoked_module="test_other"),
            dict(scope="other"),
            dict(runner_sha256=OTHER),
        ):
            with self.subTest(change=change), self.assertRaises(reuse.ReuseIneligible):
                receipt(parent=replace(observation(), **change))

    def test_partial_wrong_or_reordered_tests_cannot_be_promoted(self):
        mutations = [
            lambda r: r["discovery"].update(tests=1),
            lambda r: r["discovery"].update(tests=True),
            lambda r: r["discovery"].update(test_ids=list(reversed(IDS))),
            lambda r: r["discovery"].update(loader_errors=["import failed"]),
            lambda r: r["discovery"].update(module_names=["test_other"]),
            lambda r: r["result"].update(tests_run=1),
            lambda r: r.update(test_outcomes=r["test_outcomes"][:1]),
            lambda r: r.update(test_outcomes=list(reversed(r["test_outcomes"]))),
            lambda r: r.update(errors=[{"error": "contradiction"}]),
        ]
        for mutation in mutations:
            child = report()
            mutation(child)
            with self.subTest(report=child), self.assertRaises(reuse.ReuseIneligible):
                receipt(child=child)

    def test_skips_expected_failures_subtest_failures_and_missing_outcomes_rejected(
        self,
    ):
        for field in (
            "failures",
            "errors",
            "skipped",
            "expected_failures",
            "unexpected_successes",
        ):
            child = report()
            child["result"][field] = 1
            with self.subTest(field=field), self.assertRaises(reuse.ReuseIneligible):
                receipt(child=child)
            child["result"][field] = False
            with self.subTest(boolean=field), self.assertRaises(reuse.ReuseIneligible):
                receipt(child=child)
        for status in (
            "skipped",
            "expected_failure",
            "subtest_failure",
            "failure",
            "error",
        ):
            child = report()
            child["test_outcomes"][0]["status"] = status
            with self.subTest(status=status), self.assertRaises(reuse.ReuseIneligible):
                receipt(child=child)
        child = report()
        del child["test_outcomes"]
        with self.assertRaises(reuse.ReuseIneligible):
            receipt(child=child)

    def test_changed_inputs_and_malformed_json_prevent_terminal_pass(self):
        with self.assertRaises(reuse.ReuseIneligible):
            receipt(after=manifest(environment=OTHER))
        with self.assertRaises(reuse.ReuseIneligible):
            reuse.terminal_receipt(manifest(), manifest(), observation(), b"{partial")

    def test_store_private_pass_roundtrip_and_original_origin_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            store = reuse.LocalResultStore(Path(directory) / "results")
            candidate = manifest()
            self.assertIsNone(store.lookup(candidate))
            sealed, raw = receipt(candidate)
            original = store.publish(sealed, raw)
            self.assertEqual(original.report_bytes, raw)
            self.assertEqual(store.lookup(candidate), original)
            later, later_raw = receipt(
                candidate, parent=replace(observation(), invocation_id="later")
            )
            self.assertEqual(store.publish(later, later_raw), original)
            entry = store.root / candidate.key
            self.assertEqual(entry.stat().st_mode & 0o777, 0o700)
            for name in ("receipt.json", "report.json"):
                self.assertEqual((entry / name).stat().st_mode & 0o777, 0o600)
            self.assertEqual(original.receipt.as_dict()["origin"], "executed")
            self.assertIsNone(store.lookup(manifest(rng={"seed": 10})))

    def test_tampered_missing_and_reuse_chain_artifacts_rejected(self):
        for damage in ("report", "receipt", "missing", "chain", "symlink"):
            with self.subTest(
                damage=damage
            ), tempfile.TemporaryDirectory() as directory:
                store = reuse.LocalResultStore(Path(directory) / "results")
                sealed, raw = receipt()
                store.publish(sealed, raw)
                entry = store.root / manifest().key
                if damage == "report":
                    (entry / "report.json").write_bytes(b"{}")
                elif damage == "receipt":
                    (entry / "receipt.json").write_bytes(b"{}")
                elif damage == "missing":
                    (entry / "report.json").unlink()
                elif damage == "symlink":
                    (entry / "report.json").unlink()
                    (entry / "report.json").symlink_to(entry / "receipt.json")
                else:
                    changed = sealed.as_dict()
                    changed["origin"] = "reused"
                    (entry / "receipt.json").write_bytes(reuse.canonical_bytes(changed))
                with self.assertRaises(reuse.StoreIntegrityError):
                    store.lookup(manifest())

    def test_empty_catalog_and_external_fixture_maps_are_explicitly_supported(self):
        candidate = manifest(catalog={}, fixtures={}, oracles={})
        sealed, raw = receipt(candidate)
        self.assertEqual(sealed.as_dict()["manifest"]["catalog"], {})
        self.assertEqual(
            sealed.as_dict()["report_sha256"], hashlib.sha256(raw).hexdigest()
        )

    def test_malformed_manifest_and_receipt_raise_typed_errors(self):
        for raw in (b"{", b"\xff", b"[]", b"null"):
            with self.subTest(raw=raw), self.assertRaises(reuse.ReuseIneligible):
                reuse.ValidationManifest(raw)
            with self.subTest(receipt=raw), self.assertRaises(reuse.ReuseIneligible):
                reuse.TerminalReceipt(raw).as_dict()

    def test_declared_import_origins_required_in_terminal_artifact(self):
        origins = {"test_example": "server/tests/test_example.py"}
        candidate = manifest(policies={"import_origins": origins})
        for actual in (None, {}, {"test_example": "elsewhere/test_example.py"}):
            child = report()
            if actual is not None:
                child["import_origins"] = actual
            with self.subTest(origins=actual), self.assertRaises(reuse.ReuseIneligible):
                receipt(candidate, child=child)
        child["import_origins"] = {**origins, "unrelated": "server/other.py"}
        sealed, raw = receipt(candidate, child=child)
        with tempfile.TemporaryDirectory() as directory:
            store = reuse.LocalResultStore(Path(directory) / "results")
            self.assertEqual(store.publish(sealed, raw).report_bytes, raw)
            child["import_origins"] = {}
            altered_raw = json.dumps(child).encode()
            changed_receipt = sealed.as_dict()
            changed_receipt["report_sha256"] = hashlib.sha256(altered_raw).hexdigest()
            entry = store.root / candidate.key
            (entry / "report.json").write_bytes(altered_raw)
            (entry / "receipt.json").write_bytes(reuse.canonical_bytes(changed_receipt))
            with self.assertRaises(reuse.StoreIntegrityError):
                store.lookup(candidate)

    def test_declared_python_startup_requires_actual_exact_boolean_report(self):
        startup = dict(isolated=True, no_site=True, ignore_environment=True)
        candidate = manifest(
            policies={
                "python_import_mode": "isolated-no-site-v1",
                "python_startup": startup,
            }
        )
        for actual in (
            None,
            {},
            {**startup, "no_site": False},
            {**startup, "isolated": 1},
            {**startup, "unknown": True},
        ):
            child = report()
            if actual is not None:
                child["python_startup"] = actual
            with self.subTest(startup=actual), self.assertRaises(reuse.ReuseIneligible):
                receipt(candidate, child=child)
        child["python_startup"] = dict(startup)
        sealed, raw = receipt(candidate, child=child)
        with tempfile.TemporaryDirectory() as directory:
            store = reuse.LocalResultStore(Path(directory) / "results")
            self.assertEqual(store.publish(sealed, raw).report_bytes, raw)
