"""eWN.C source-value transform precedes eZR forced-value context."""
import unittest
from dataclasses import asdict, replace

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_event_replay import NativeEventSource
from wakfu_server.combat_final_modifier import final_modifier_source
from wakfu_server.combat_maximum_resource import maximum_application_amount
from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
from wakfu_server.combat_value_transfer import transfer_value_context


class MaximumTriggerTransformTests(unittest.TestCase):
    def invocation(self, value):
        source = NativeEventSource(
            uid=100,
            generic_effect=200,
            value=value,
            caster_id=7,
            target_id=7,
            cell=(0, 0, 0),
            event_ids=(0,),
            channel=3,
            manager_actor_id=7,
            source_parent_uid=None,
            suppresses_level_one=False,
            suppresses_all=False,
            suppressed=False,
            native_events_verified=True,
            effect_action_id=31,
        )
        return source, EffectInvocation(
            300, 1, 7, 7, (0, 0, 0), native_trigger_context=asdict(source)
        )

    def test_positive_trigger_doubles_with_java_overflow(self):
        for value, expected in ((6, 12), ((1 << 30), -(1 << 31))):
            with self.subTest(value=value):
                _, invocation = self.invocation(value)
                self.assertEqual(maximum_application_amount(-2, invocation), expected)

    def test_null_or_nonpositive_trigger_keeps_literal_minus_two(self):
        invocation = EffectInvocation(300, 1, 7, 7, (0, 0, 0))
        self.assertEqual(maximum_application_amount(-2, invocation), -2)
        for value in (0, -4):
            _, invocation = self.invocation(value)
            self.assertEqual(maximum_application_amount(-2, invocation), -2)

    def test_forced_context_applies_after_trigger_transform(self):
        _, invocation = self.invocation(6)
        invocation = replace(
            invocation, native_context_hex=transfer_value_context(b"", 9).hex()
        )
        self.assertEqual(maximum_application_amount(-2, invocation), 9)

    def test_live_runner_value_wins_over_earlier_source_snapshot(self):
        source, invocation = self.invocation(6)
        runner = NativeRunnerAmount(source.uid, 31, rng=lambda: 0.5, value=11)
        with final_modifier_source(replace(source, runner_modifier=runner)):
            self.assertEqual(maximum_application_amount(-2, invocation), 22)

    def test_mismatched_live_source_rejects(self):
        source, invocation = self.invocation(6)
        with final_modifier_source(replace(source, uid=101)):
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                maximum_application_amount(-2, invocation)

    def test_state_controller_metadata_does_not_hide_actual_qe_value(self):
        _, invocation = self.invocation(6)
        invocation = replace(
            invocation,
            native_trigger_context={
                **invocation.native_trigger_context,
                "native_source_is_eWu": True,
                "native_apply_state_reference": 1733,
                "effect_action_id": 304,
            },
        )
        self.assertEqual(maximum_application_amount(-2, invocation), 12)
