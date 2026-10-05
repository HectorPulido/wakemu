"""Distinguish installed listeners, actual activation and incomplete traces."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_passive_activation import summarize_stage, passive_cases


class PassiveActivationEvidenceTests(unittest.TestCase):
    def stage(self, events):
        state = {"actors": {}, "native_retained_records": {}}
        return summarize_stage("turn", events, state, state, (), {10})

    def test_subscription_registration_is_not_activation(self):
        events = [
            dict(
                event="combat_effect",
                effect_reference=10,
                status=status,
                ancestors=[10],
            )
            for status in ("subscribed_waiting_event", "completed")
        ]
        self.assertFalse(self.stage(events)["passive_activation_observed"])

    def test_completed_child_of_listener_is_attributed(self):
        events = [
            dict(
                event="combat_effect",
                effect_reference=11,
                status="completed",
                ancestors=[10, 11],
            )
        ]
        self.assertTrue(self.stage(events)["passive_activation_observed"])

    def test_trace_truncation_is_explicit_not_silent(self):
        stage = self.stage(
            [
                dict(
                    event="combat_effect_trace_summary",
                    effects_logged=8192,
                    effects_omitted=4,
                )
            ]
        )
        self.assertFalse(stage["trace_complete"])
        self.assertFalse(stage["passive_activation_observed"])

    def test_focal_selection_keeps_native_identity_and_legal_level(self):
        rows = passive_cases(11, identities=[5051], level=200)
        self.assertEqual(
            [(r["id"], r["breed"], r["level"]) for r in rows], [(5051, 11, 200)]
        )
        with self.assertRaises(ValueError):
            passive_cases(12, identities=[5051], level=200)
        with self.assertRaises(ValueError):
            passive_cases(11, identities=[5051], level=1)
