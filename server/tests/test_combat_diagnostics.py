import unittest
from wakfu_server.combat_diagnostics import combat_diagnostic_scope, effect_step, diagnostics_enabled


class DiagnosticsTests(unittest.TestCase):
    def test_bounded_trace_and_cleanup_after_failure(self):
        rows = []
        with self.assertRaisesRegex(ValueError, "cast rejected"):
            with combat_diagnostic_scope(lambda **row: rows.append(row), limit=2):
                for reference in (1, 2, 3):
                    effect_step(effect_reference=reference, status="completed")
                raise ValueError("cast rejected")
        self.assertFalse(diagnostics_enabled())
        self.assertEqual([r.get("effect_reference") for r in rows[:-1]], [1, 2])
        self.assertEqual(rows[-1], dict(event="combat_effect_trace_summary", effects_logged=2, effects_omitted=1))

    def test_nested_requests_restore_own_sink_and_reject_private_fields(self):
        first, second = [], []
        with combat_diagnostic_scope(lambda **row: first.append(row)):
            with combat_diagnostic_scope(lambda **row: second.append(row)):
                effect_step(effect_reference=20)
                with self.assertRaisesRegex(ValueError, "Unapproved"):
                    effect_step(password="must never be emitted")
            effect_step(effect_reference=10)
        self.assertEqual(first[0]["effect_reference"], 10)
        self.assertEqual(second[0]["effect_reference"], 20)
        self.assertNotIn("password", str(first + second))
