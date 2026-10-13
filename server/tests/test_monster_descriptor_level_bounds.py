"""Pure tests for optional descriptor level proof bounds."""
import ast
from pathlib import Path
import unittest


VALIDATOR = (
    Path(__file__).resolve().parents[1] / "tools/validate_monster_spell_activation.py"
)


def load_functions(*names):
    tree = ast.parse(VALIDATOR.read_text())
    selected = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    namespace = {}
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), str(VALIDATOR), "exec"),
        namespace,
    )
    return namespace


class DescriptorLevelBoundTests(unittest.TestCase):
    def setUp(self):
        self.functions = load_functions(
            "bounded_reference_rows", "validate_receipt_context"
        )
        self.bound = self.functions["bounded_reference_rows"]

    def test_default_and_maximum_behavior_remain_unchanged(self):
        rows = [dict(ref=1, min_level=1, max_level=80, spell_ids=[7])]
        self.assertEqual(self.bound(rows, {1}), rows)
        self.assertEqual(
            self.bound(rows, {1}, 49),
            [dict(ref=1, min_level=1, max_level=49, spell_ids=[7])],
        )
        self.assertEqual(rows[0]["max_level"], 80)

    def test_minimum_and_combined_bounds_clip_only_proof_rows(self):
        rows = [
            dict(ref=1, min_level=1, max_level=80),
            dict(ref=2, min_level=55, max_level=75),
        ]
        self.assertEqual(
            self.bound(rows, {1, 2}, minimum_level=50),
            [
                dict(ref=1, min_level=50, max_level=80),
                dict(ref=2, min_level=55, max_level=75),
            ],
        )
        self.assertEqual(
            self.bound(rows, {1, 2}, 60, 50),
            [
                dict(ref=1, min_level=50, max_level=60),
                dict(ref=2, min_level=55, max_level=60),
            ],
        )
        self.assertEqual(
            rows,
            [
                dict(ref=1, min_level=1, max_level=80),
                dict(ref=2, min_level=55, max_level=75),
            ],
        )

    def test_sparse_and_nonoverlapping_rows_are_preserved_or_excluded(self):
        rows = [
            dict(ref=1, min_level=1, max_level=49),
            dict(ref=2, min_level=50, max_level=60),
            dict(ref=3, min_level=70, max_level=80),
        ]
        self.assertEqual(
            self.bound(rows, {1, 2, 3}, minimum_level=50, maximum_level=75),
            [
                dict(ref=2, min_level=50, max_level=60),
                dict(ref=3, min_level=70, max_level=75),
            ],
        )
        self.assertEqual(self.bound(rows, {1}, minimum_level=50), [])
        self.assertEqual(self.bound(rows, {3}, maximum_level=60), [])

    def test_invalid_bounds_reject(self):
        rows = [dict(ref=1, min_level=1, max_level=80)]
        for value in (True, 0, -1, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.bound(rows, {1}, minimum_level=value)
        with self.assertRaises(ValueError):
            self.bound(rows, {1}, minimum_level=51, maximum_level=50)

    def test_receipt_reuse_requires_identical_minimum_and_maximum_bounds(self):
        required = dict(
            candidate_manifest_sha256="m",
            changed_document_hashes={},
            base_revision="b",
            base_document_hashes={},
            runtime_code_sha256={},
            native_monsters_sha256="n",
            validator_sha256="v",
            test_code_sha256={},
            test_scope=[],
        )
        previous = dict(
            required, maximum_descriptor_level=80, minimum_descriptor_level=50
        )
        self.functions["validate_receipt_context"](previous, dict(previous))
        for field, value in (
            ("minimum_descriptor_level", 49),
            ("maximum_descriptor_level", 79),
        ):
            current = dict(previous, **{field: value})
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "descriptor proof bounds"
            ):
                self.functions["validate_receipt_context"](previous, current)

    def test_cli_passes_minimum_bound_into_proof_and_receipt(self):
        tree = ast.parse(VALIDATOR.read_text())
        main = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        source = ast.unparse(main)
        self.assertIn("parser.add_argument('--min-descriptor-level', type=int)", source)
        self.assertIn("args.max_descriptor_level, args.min_descriptor_level", source)
        self.assertIn(
            "result['minimum_descriptor_level'] = args.min_descriptor_level", source
        )


if __name__ == "__main__":
    unittest.main()
