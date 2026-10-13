import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from monster_activation_work_queue import (
    build,
    complete,
    fingerprint,
    invalidate,
    load,
    representatives,
    reusable,
    save,
)


class MonsterActivationWorkQueueTests(unittest.TestCase):
    def row(self, ref=1, low=1, high=60):
        return dict(
            ref=ref, name="native", min_level=low, max_level=high, category="blocked"
        )

    def queue(self, rows):
        return build(
            dict(remaining_monsters=rows, revision="sealed", enabled=1094),
            dict(groups=[dict(id="shared", signature="native", refs=[1, 2])]),
        )

    def test_exclusive_boundary_preserves_native_maximum(self):
        queue = self.queue([self.row(1, 49, 60), self.row(3, 50, 60)])
        self.assertEqual(
            [(j["ref"], j["max_level"], j["native_max_level"]) for j in queue["jobs"]],
            [(1, 49, 60)],
        )
        for low in (True, 0, 1.5):
            with self.assertRaises(ValueError):
                self.queue([self.row(low=low)])

    def test_duplicate_reference_and_overlapping_causal_groups_reject(self):
        with self.assertRaises(ValueError):
            self.queue([self.row(), self.row()])
        with self.assertRaises(ValueError):
            build(
                dict(remaining_monsters=[], revision="x", enabled=0),
                dict(groups=[dict(refs=[1]), dict(refs=[1])]),
            )

    def test_cache_requires_all_exact_dependency_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = [
                Path(tmp) / name
                for name in ("candidate", "runtime", "tests", "catalog", "recipe")
            ]
            for p in files:
                p.write_text("sealed")
            raw = Path(tmp) / "receipt.json"
            raw.write_text("{}")
            job = dict(
                state="blocked",
                execution_dependencies=fingerprint(dict.fromkeys(files)),
                evidence=dict(
                    path=str(raw), sha256=hashlib.sha256(raw.read_bytes()).hexdigest()
                ),
            )
            self.assertTrue(reusable(job))
            for p in files:
                p.write_text("changed")
                self.assertFalse(reusable(job))
                p.write_text("sealed")
            files[0].unlink()
            self.assertFalse(reusable(job))

    def test_invalidation_only_affects_dependent_non_enabled_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "source"
            p.write_text("x")
            deps = fingerprint({p: None})
            q = dict(
                jobs=[
                    dict(ref=1, state="blocked", execution_dependencies=deps),
                    dict(ref=2, state="enabled", execution_dependencies=deps),
                    dict(ref=3, state="blocked", execution_dependencies=None),
                ]
            )
            self.assertEqual(invalidate(q, [p]), [1])
            self.assertEqual(q["jobs"][1]["state"], "enabled")

    def test_interrupted_checkpoint_retains_attempt_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = self.queue([self.row()])
            q["jobs"][0].update(state="running", attempts=[{"error": "prior"}])
            p = Path(tmp) / "queue.json"
            save(p, q)
            restored = load(p)
            self.assertEqual(restored["jobs"][0]["state"], "retryable")
            self.assertEqual(restored["jobs"][0]["attempts"], [{"error": "prior"}])
            self.assertFalse(p.with_name("queue.json.tmp").exists())

    def test_representatives_deterministic_unique_and_largest_first(self):
        q = self.queue([self.row(3), self.row(2), self.row(1)])
        reps = representatives(q)
        self.assertEqual([r["representative"] for r in reps], [1, 3])
        self.assertEqual(reps[0]["affected_refs"], [1, 2])

    def test_partial_approval_rejects_without_mutating_job(self):
        job = self.queue([self.row()])["jobs"][0]
        before = repr(job)
        with self.assertRaises(ValueError):
            complete(
                job,
                dependencies={},
                receipt=dict(ref=1, status="execution_approved"),
                elapsed_seconds=1,
            )
        self.assertEqual(repr(job), before)

    def test_unknown_dependency_and_nonterminal_state_never_reuse(self):
        self.assertFalse(reusable(dict(state="blocked", execution_dependencies=None)))
        self.assertFalse(
            reusable(dict(state="retryable", execution_dependencies={"/missing": "x"}))
        )
        with self.assertRaises(ValueError):
            fingerprint({})


class WorkerEvidenceTests(unittest.TestCase):
    def fixture(self, tmp):
        source = Path(tmp) / "source"
        source.write_text("sealed")
        raw = Path(tmp) / "raw.json"
        ai = dict(
            status="validated",
            packets=1,
            forecast_source_unchanged=True,
            serializer_failure_rolled_back=True,
            committed_state_changed=True,
            owned_object_identities_preserved=True,
        )
        document = dict(
            monsters=[
                dict(
                    ref=1,
                    status="validated",
                    cases=[
                        dict(
                            level=1,
                            spell_id=7,
                            status="validated",
                            successful_targets=[dict(effectful=True)],
                        )
                    ],
                    ai_commit=ai,
                )
            ]
        )
        raw.write_text(json.dumps(document))
        receipt = dict(
            ref=1,
            status="execution_approved",
            level_range=[1, 1],
            evidence=dict(
                path=str(raw), sha256=hashlib.sha256(raw.read_bytes()).hexdigest()
            ),
        )
        for key in (
            "full_native_book",
            "native_initialization_proven",
            "actual_ai_commit",
            "forecast_source_unchanged",
            "serializer_failure_rolled_back",
            "committed_state_changed",
            "owned_object_identities_preserved",
        ):
            receipt[key] = True
        job = dict(
            ref=1, min_level=1, max_level=1, spell_ids=[7], state="running", attempts=[]
        )
        return job, source, raw, receipt

    def test_real_raw_fixture_approval_and_mutated_receipt_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            job, source, raw, receipt = self.fixture(tmp)
            complete(
                job,
                dependencies=fingerprint({source: None}),
                receipt=receipt,
                elapsed_seconds=1,
            )
            self.assertTrue(reusable(job))
            raw.write_text("{}")
            self.assertFalse(reusable(job))

    def test_arbitrary_json_or_missing_receipt_never_approves(self):
        with tempfile.TemporaryDirectory() as tmp:
            job, source, raw, receipt = self.fixture(tmp)
            raw.write_text("{}")
            receipt["evidence"]["sha256"] = hashlib.sha256(raw.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                complete(
                    job,
                    dependencies=fingerprint({source: None}),
                    receipt=receipt,
                    elapsed_seconds=1,
                )
            raw.unlink()
            with self.assertRaises(OSError):
                complete(
                    job,
                    dependencies=fingerprint({source: None}),
                    receipt=receipt,
                    elapsed_seconds=1,
                )
            self.assertEqual(job["state"], "running")
            self.assertEqual(job["attempts"], [])

    def test_changed_dependency_during_execution_rejects_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            job, source, raw, receipt = self.fixture(tmp)
            before = fingerprint({source: None})
            source.write_text("changed")
            with self.assertRaises(ValueError):
                complete(job, dependencies=before, receipt=receipt, elapsed_seconds=1)
            self.assertEqual(job["state"], "running")
            self.assertEqual(job["attempts"], [])

    def test_wrong_or_missing_owned_book_rejects_raw_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            job, source, raw, receipt = self.fixture(tmp)
            for book in ([], [8]):
                job["spell_ids"] = book
                with self.assertRaises(ValueError):
                    complete(
                        job,
                        dependencies=fingerprint({source: None}),
                        receipt=receipt,
                        elapsed_seconds=1,
                    )
            self.assertEqual(job["state"], "running")
