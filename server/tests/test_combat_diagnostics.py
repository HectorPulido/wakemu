import unittest
from wakfu_server.combat_diagnostics import (
    combat_diagnostic_scope,
    effect_step,
    diagnostics_enabled,
)


class DiagnosticsTests(unittest.TestCase):
    def test_failed_effect_identifies_family_target_and_call_chain(self):
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            EffectInvocation,
            UnsupportedEffectExecution,
        )
        from wakfu_server.combat_conditions import ConditionContext

        rows = []
        definition = dict(
            effect_class=949,
            parameters=[],
            parameter_count=0,
            probability_base=100,
            probability_per_level=0,
            minimum_level=1,
            maximum_level=200,
            criteria="",
            children=[],
        )
        dispatcher = EffectDispatcher(
            {"80": definition},
            {},
            resolve=lambda effect, invocation: (invocation,),
            condition_context=lambda invocation: ConditionContext({}),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda identity: (0, 0, 0),
        )
        with combat_diagnostic_scope(lambda **row: rows.append(row)):
            with self.assertRaisesRegex(
                UnsupportedEffectExecution, "Native949 requires eZM context authority"
            ):
                dispatcher.execute(
                    EffectInvocation(80, 20, 7, -7, (1, 0, 0)), ancestors=(90,)
                )
        row = rows[0]
        self.assertEqual(
            (row["status"], row["effect_reference"], row["effect_class"]),
            ("failed", 80, 949),
        )
        self.assertEqual(row["ancestors"], (90, 80))
        self.assertEqual(row["target_id"], -7)
        self.assertIn("949", row["reason"])
        self.assertGreaterEqual(row["elapsed_ms"], 0)

    def test_bounded_trace_and_cleanup_after_failure(self):
        rows = []
        with self.assertRaisesRegex(ValueError, "cast rejected"):
            with combat_diagnostic_scope(lambda **row: rows.append(row), limit=2):
                for reference in (1, 2, 3):
                    effect_step(effect_reference=reference, status="completed")
                raise ValueError("cast rejected")
        self.assertFalse(diagnostics_enabled())
        self.assertEqual([r.get("effect_reference") for r in rows[:-1]], [1, 2])
        self.assertEqual(
            rows[-1],
            dict(
                event="combat_effect_trace_summary", effects_logged=2, effects_omitted=1
            ),
        )

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
