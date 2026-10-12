import unittest
from monster_initialization_diagnostic import initialization_diagnostic


class DiagnosticTests(unittest.TestCase):
    def evaluate(self, cases):
        return initialization_diagnostic(
            5661,
            [8649, 1, 1],
            248,
            253,
            cases,
            proven=lambda ref, level, triples, r: r.get("verified") is True,
        )

    def test_verified_first_level_cast_failure_is_unvisited_coverage(self):
        row = self.evaluate(
            [
                dict(
                    level=248,
                    initialization_receipts=[{"verified": True}],
                    errors={"ValueError: retained": 2},
                )
            ]
        )
        self.assertTrue(row["pending"])
        self.assertEqual(row["failed_levels"], [])
        self.assertEqual(row["unvisited_levels"], [249, 250, 251, 252, 253])
        self.assertEqual(row["reason"], "native_initial_state_coverage_incomplete")

    def test_actual_constructor_failure_retains_failure_label(self):
        row = self.evaluate(
            [dict(level=248, errors={"initialization: ValueError: missing": 4})]
        )
        self.assertEqual(row["failed_levels"], [248])
        self.assertTrue(row["pending"])
        self.assertEqual(row["reason"], "native_initial_states_not_initialized")

    def test_all_levels_must_have_real_proof(self):
        row = self.evaluate(
            [
                dict(level=i, initialization_receipts=[{"verified": True}])
                for i in range(248, 254)
            ]
        )
        self.assertFalse(row["pending"])
        self.assertIsNone(row["reason"])


class CaseCoverageTests(unittest.TestCase):
    def test_failfast_first_level_does_not_mean_constructor_failure(self):
        from monster_initialization_diagnostic import native_case_coverage

        result = native_case_coverage(1, 3, [7, 8], [dict(level=1, spell_id=7)])
        self.assertEqual(result["expected_native_case_count"], 6)
        self.assertEqual(result["unvisited_native_case_count"], 5)
        self.assertFalse(result["full_native_case_coverage"])

    def test_foreign_duplicate_cases_never_fill_missing_coverage(self):
        from monster_initialization_diagnostic import native_case_coverage

        result = native_case_coverage(
            1, 1, [7, 8], [dict(level=1, spell_id=7)] * 2 + [dict(level=2, spell_id=8)]
        )
        self.assertEqual(result["visited_native_case_count"], 1)
        self.assertEqual(result["duplicate_case_count"], 1)
        self.assertEqual(result["foreign_case_count"], 1)
        self.assertFalse(result["full_native_case_coverage"])

    def test_full_case_scope_counted_exactly(self):
        from monster_initialization_diagnostic import native_case_coverage

        result = native_case_coverage(
            1, 2, [7], [dict(level=n, spell_id=7) for n in (1, 2)]
        )
        self.assertTrue(result["full_native_case_coverage"])

    def test_nonempty_unproven_receipt_stays_pending(self):
        result = initialization_diagnostic(
            1,
            [5, 1, 1],
            1,
            1,
            [dict(level=1, initialization_receipts=[{}])],
            proven=lambda *args: False,
        )
        self.assertTrue(result["pending"])
        self.assertEqual(result["unproven_attempted_levels"], [1])
        self.assertEqual(result["unvisited_levels"], [])


class GatePreservationTests(unittest.TestCase):
    def test_original_eligibility_expressions_and_proof_functions_unchanged(self):
        import ast
        from pathlib import Path

        original = ast.parse(
            Path("server/tools/validate_monster_spell_activation.py").read_text()
        )
        proposed = ast.parse(
            (
                Path(__file__).resolve().parents[1]
                / "tools/validate_monster_spell_activation.py"
            ).read_text()
        )

        def gates(tree):
            result = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in (
                    "initialization_proven",
                    "case_qualification_complete",
                ):
                    result.append(ast.dump(node))
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name)
                    and target.id in ("status", "pending_initialization")
                    for target in node.targets
                ):
                    result.append(ast.dump(node))
            return sorted(result)

        self.assertEqual(gates(original), gates(proposed))
