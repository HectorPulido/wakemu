"""Casting trace audits distinguish decisions from incidental false hooks."""
import unittest
from audit_monster_casting_rejections import rejection_groups


class CastingRejectionAuditTests(unittest.TestCase):
    def row(self, code, trace, status="pending"):
        return dict(
            ref=42,
            result=dict(
                status=status,
                cast_diagnostics=[
                    dict(
                        details=dict(
                            native_casting_result=code,
                            native_casting_diagnostic=dict(trace=trace),
                        )
                    )
                ],
            ),
        )

    def test_terminal_hook_precedes_result_and_ignores_followup_details(self):
        row = self.row(
            "twV",
            [
                dict(stage="root_has_shape", value=False),
                dict(stage="criterion_cell", value=False),
                dict(stage="result", value="twV"),
                dict(stage="native_los_detail", value={}),
            ],
        )
        group = rejection_groups([row, row])[0]
        self.assertEqual(group["terminal_hook"], "criterion_cell")
        self.assertEqual(group["references"], [42])
        self.assertEqual(group["observations"], 2)

    def test_passed_representatives_are_not_reclassified_by_failed_attempts(self):
        row = self.row("twI", [dict(stage="range_accepts", value=False)], "validated")
        self.assertEqual(rejection_groups([row]), [])

    def test_inconsistent_result_rejects(self):
        with self.assertRaises(ValueError):
            rejection_groups([self.row("twI", [dict(stage="result", value="twV")])])
