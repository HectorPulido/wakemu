"""Detached constructors accept instantaneous states without inventing clocks."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat.combat_summon_initial_states import initial_state_plan
from wakfu_server.combat.combat_summon_initialization import install_initial_states


class InitialStateZeroDurationTests(unittest.TestCase):
    def run_profile(self, duration, realtime=0):
        actor = SimpleNamespace(id=-3, position=(0, 0, 0))
        fight = SimpleNamespace()
        contexts = []
        handler = SimpleNamespace(fight=fight, catalog={})

        def apply(*args, **kwargs):
            contexts.append(kwargs["carrier_context"])
            return True

        dispatcher = SimpleNamespace(
            native_state_handler=handler,
            native_retention=SimpleNamespace(apply_state_reference=apply),
        )
        profile = dict(duration=duration, realtime_duration=realtime)
        with patch(
            "wakfu_server.combat.combat_summon_initialization.detached_actor",
            return_value=actor,
        ), patch(
            "wakfu_server.combat.combat_definitions.state_profile", return_value=profile
        ):
            install_initial_states(
                fight,
                actor,
                initial_state_plan([2354, 1, 0], 1),
                runtime_factory=lambda *args: (dispatcher, []),
            )
        return contexts

    def test_zero_duration_keeps_native_clock_and_has_no_timeline(self):
        (context,) = self.run_profile(0)
        self.assertEqual(context.native_turn_clock, 0)
        self.assertEqual(context.native_realtime_remaining, 0)
        self.assertIsNone(context.timeline)
        self.assertFalse(context.applying_effect_has_delay)

    def test_indefinite_constructor_keeps_existing_clock(self):
        (context,) = self.run_profile(-1)
        self.assertEqual(context.native_turn_clock, -1)
        self.assertIsNone(context.timeline)

    def test_finite_positive_duration_stays_rejected(self):
        with self.assertRaisesRegex(ValueError, "audited finite timeline"):
            self.run_profile(1)

    def test_positive_realtime_stays_rejected(self):
        with self.assertRaisesRegex(ValueError, "audited finite timeline"):
            self.run_profile(0, 1)
