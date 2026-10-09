"""Reactions read the mutable Qe instead of its earlier event descriptor."""
import unittest
from dataclasses import asdict, replace

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_event_replay import NativeEventSource
from wakfu_server.combat_final_modifier import final_modifier_source
from wakfu_server.combat_trigger_value import triggering_value
from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount


class LiveTriggerValueTests(unittest.TestCase):
    def source(self):
        return NativeEventSource(
            uid=100,
            generic_effect=200,
            value=6,
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

    def test_sibling_mutation_is_visible_without_changing_descriptor(self):
        source = self.source()
        invocation = EffectInvocation(
            300, 1, 7, 7, (0, 0, 0), native_trigger_context=asdict(source)
        )
        runner = NativeRunnerAmount(100, 31, rng=lambda: 0.5, value=6)
        with final_modifier_source(replace(source, runner_modifier=runner)):
            self.assertEqual(triggering_value(invocation), 6)
            runner.set_applied(11)
            self.assertEqual(triggering_value(invocation), 11)
        self.assertEqual(invocation.native_trigger_context["value"], 6)

    def test_other_live_source_is_rejected(self):
        source = self.source()
        invocation = EffectInvocation(
            300, 1, 7, 7, (0, 0, 0), native_trigger_context=asdict(source)
        )
        with final_modifier_source(replace(source, uid=101)):
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                triggering_value(invocation)
