from copy import deepcopy
import signal
import time
import unittest

from consume_monster_fullbook_completions import completed_books, context_deadline


class FullbookCompletionConsumerTests(unittest.TestCase):
    def fixture(self):
        keys = [(7, 20, 100, 4), (7, 20, 101, 0)]
        job = dict(reference=7, actor_level=20, exact_contexts=keys)
        proofs = {
            key: dict(raw_case=dict(status="validated", initialization_receipts=[]))
            for key in keys
        }
        native = {7: dict(raw_native=dict(cle=[]))}
        return job, proofs, native

    def test_every_exact_tuple_required_without_owner_or_spell_level_transfer(self):
        job, proofs, native = self.fixture()
        self.assertEqual(len(completed_books([job], proofs, native)), 1)
        for replacement in ((8, 20, 101, 0), (7, 20, 101, 1), (7, 21, 101, 0)):
            shifted = deepcopy(proofs)
            shifted[replacement] = shifted.pop((7, 20, 101, 0))
            self.assertEqual(completed_books([job], shifted, native), [])

    def test_constructor_receipt_requires_exact_native_triples_descriptor_and_owner(
        self,
    ):
        job, proofs, native = self.fixture()
        native[7]["raw_native"]["cle"] = [[9, 2, 3]]
        self.assertEqual(completed_books([job], proofs, native), [])
        valid = dict(
            ref=7, descriptor_level=20, raw_triples=[[9, 2, 3]], initialized=True
        )
        row = proofs[(7, 20, 100, 4)]["raw_case"]
        for field, value in [
            ("ref", 8),
            ("descriptor_level", 21),
            ("raw_triples", [[9, 2, 4]]),
            ("initialized", False),
        ]:
            receipt = dict(valid)
            receipt[field] = value
            row["initialization_receipts"] = [receipt]
            self.assertEqual(completed_books([job], proofs, native), [])
        row["initialization_receipts"] = [valid]
        self.assertEqual(len(completed_books([job], proofs, native)), 1)

    def test_raw_pending_never_becomes_complete_by_spell_id(self):
        job, proofs, native = self.fixture()
        proofs[(7, 20, 101, 0)]["raw_case"]["status"] = "pending"
        self.assertEqual(completed_books([job], proofs, native), [])

    def test_wall_clock_alarm_raises_and_restores_handler_and_timer(self):
        for seconds in (0, -1, 61):
            with self.assertRaises(ValueError):
                with context_deadline(seconds):
                    self.fail("invalid budget entered")
        handler = signal.getsignal(signal.SIGALRM)
        timer = signal.getitimer(signal.ITIMER_REAL)
        self.assertEqual(timer, (0.0, 0.0))
        with self.assertRaisesRegex(TimeoutError, "wall-clock"):
            with context_deadline(0.01):
                time.sleep(0.1)
        self.assertIs(signal.getsignal(signal.SIGALRM), handler)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), timer)

    def test_actual_worker_completion_statuses_without_relabeling(self):
        from consume_monster_fullbook_completions import worker_completed

        for status in ("completed_missing_native_contexts", "completed"):
            report = {"status": status}
            self.assertTrue(worker_completed(report))
            self.assertEqual(report, {"status": status})
        self.assertFalse(worker_completed({"status": "running"}))
        self.assertFalse(worker_completed(None))

    def test_nonvalidated_case_requires_explicit_original_qualifier(self):
        job, proofs, native = self.fixture()
        proofs[(7, 20, 101, 0)]["raw_case"]["status"] = "native_zero_amount_unavailable"
        self.assertEqual(completed_books([job], proofs, native), [])
        self.assertEqual(
            completed_books([job], proofs, native, qualifier=lambda case: False), []
        )
        seen = []
        self.assertEqual(
            len(
                completed_books(
                    [job],
                    proofs,
                    native,
                    qualifier=lambda case: seen.append(case) or True,
                )
            ),
            1,
        )
        self.assertEqual(len(seen), 2)

    def test_original_proof_requires_actual_enclosing_owner_not_requested_label(self):
        import json
        import tempfile
        from pathlib import Path
        from consume_monster_fullbook_completions import original_proof, checksum

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "original.json"
            case = dict(level=20, spell_id=100, spell_level=4, status="validated")
            for owner in (8, None):
                row = dict(cases=[case])
                if owner is not None:
                    row["ref"] = owner
                path.write_text(json.dumps(dict(monsters=[row])))
                with self.assertRaisesRegex(ValueError, "enclosing owner"):
                    original_proof(
                        path, checksum(path), "/monsters/0/cases/0", (7, 20, 100, 4)
                    )
            path.write_text(json.dumps(dict(monsters=[dict(ref=7, cases=[case])])))
            self.assertEqual(
                original_proof(
                    path, checksum(path), "/monsters/0/cases/0", (7, 20, 100, 4)
                )["context"],
                (7, 20, 100, 4),
            )
