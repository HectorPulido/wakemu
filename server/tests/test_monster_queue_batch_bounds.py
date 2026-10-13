import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from monster_activation_work_queue import complete, fingerprint
import test_monster_activation_work_queue as queue_test_fixtures


class QueueBatchBoundsTests(unittest.TestCase):
    def selector(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "tools/validate_monster_spell_activation.py"
        )
        node = next(
            n
            for n in ast.parse(source.read_text()).body
            if isinstance(n, ast.FunctionDef) and n.name == "bounded_reference_rows"
        )
        namespace = {}
        exec(
            compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        return namespace[node.name]

    def test_default_retains_native_levels_without_mutation(self):
        rows = [dict(ref=1, min_level=2, max_level=70)]
        before = copy.deepcopy(rows)
        self.assertEqual(self.selector()(rows, {1}), rows)
        self.assertEqual(rows, before)

    def test_cross50_bounds_descriptor_proof_only(self):
        rows = [dict(ref=1, min_level=40, max_level=70, spell_ids=[7])]
        self.assertEqual(self.selector()(rows, {1}, 49)[0]["max_level"], 49)
        self.assertEqual(rows[0]["max_level"], 70)

    def test_native_minimum50_excluded_and_selection_respected(self):
        rows = [
            dict(ref=1, min_level=50, max_level=70),
            dict(ref=2, min_level=1, max_level=2),
        ]
        self.assertEqual(self.selector()(rows, {1}, 49), [])

    def test_invalid_proof_bounds_reject(self):
        for bound in (True, 0, -1, 1.5):
            with self.assertRaises(ValueError):
                self.selector()([], {1}, bound)

    def test_passive_requires_explicit_trusted_case_qualifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            (
                job,
                source,
                raw,
                receipt,
            ) = queue_test_fixtures.WorkerEvidenceTests().fixture(tmp)
            data = json.loads(raw.read_text())
            data["monsters"][0]["cases"][0] = dict(
                level=1, spell_id=7, status="passive_initialization_only"
            )
            raw.write_text(json.dumps(data))
            receipt["evidence"]["sha256"] = hashlib.sha256(raw.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                complete(
                    job,
                    dependencies=fingerprint({source: None}),
                    receipt=receipt,
                    elapsed_seconds=1,
                )
            seen = []
            complete(
                job,
                dependencies=fingerprint({source: None}),
                receipt=receipt,
                elapsed_seconds=1,
                case_qualifier=lambda case: seen.append(case) or True,
            )
            self.assertEqual(len(seen), 1)
            self.assertEqual(job["state"], "execution_approved")

    def test_duplicate_native_cases_reject_before_callback(self):
        with tempfile.TemporaryDirectory() as tmp:
            (
                job,
                source,
                raw,
                receipt,
            ) = queue_test_fixtures.WorkerEvidenceTests().fixture(tmp)
            data = json.loads(raw.read_text())
            data["monsters"][0]["cases"] *= 2
            raw.write_text(json.dumps(data))
            receipt["evidence"]["sha256"] = hashlib.sha256(raw.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                complete(
                    job,
                    dependencies=fingerprint({source: None}),
                    receipt=receipt,
                    elapsed_seconds=1,
                    case_qualifier=lambda _: self.fail("duplicate reached qualifier"),
                )

    def test_batch_calls_native_once_then_original_commit_without_publication(self):
        source = (
            Path(__file__).resolve().parents[1] / "tools/qualify_monster_queue_batch.py"
        )
        tree = ast.parse(source.read_text())
        main = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"
        )
        calls = [
            n
            for n in ast.walk(main)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "validator"
        ]
        native = [n for n in calls if n.func.attr == "main"]
        commit = [n for n in calls if n.func.attr == "commit_smoke"]
        self.assertEqual(len(native), 1)
        self.assertEqual(len(commit), 1)
        self.assertLess(native[0].lineno, commit[0].lineno)
        self.assertFalse(
            any(
                isinstance(n, ast.Name) and n.id in {"publish", "finalize", "deploy"}
                for n in ast.walk(main)
            )
        )
