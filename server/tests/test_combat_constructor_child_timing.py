"""eZQ/PO detached descriptor children retain without inventing SU clocks."""
from dataclasses import replace
import unittest

import test_combat_maximum_detached_constructor as fixture
from wakfu_server.combat_native_timing_context import (
    NativeEffectTimingProvider,
    native_time_payload,
)


class ConstructorChildTimingTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.DetachedMaximumConstructorTests()
        self.f.setUp()
        self.provider = NativeEffectTimingProvider({})
        self.effect = dict(
            native_execution_mode=2,
            native_definition_class="eVy",
            native_timing_definition=dict(
                ryE=2,
                ryF=0,
                ryH=0,
                ryI=0,
                clock_on_caster=True,
                clock_on_target=False,
                esr=False,
                ryG=True,
            ),
        )

    def context(self, invocation=None):
        return self.provider.stat(
            self.f.f.fight,
            None,
            self.effect,
            invocation or self.f.f.invocation,
        )

    def test_actual_constructor_keeps_retention_and_native_no_clock_sentinel(self):
        with self.f.scope():
            context = self.context()
        self.assertTrue(context.retained)
        self.assertIsNone(context.timer)
        self.assertEqual(context.timing_payload, native_time_payload())
        self.assertNotIn(self.f.actor.id, self.f.f.fight.actors)

    def test_placement_outside_constructor_still_rejects_missing_turn(self):
        with self.assertRaisesRegex(ValueError, "active actor turn"):
            self.context()

    def test_constructor_does_not_grant_foreign_target_no_clock_context(self):
        with self.f.scope(), self.assertRaisesRegex(ValueError, "active actor turn"):
            self.context(replace(self.f.f.invocation, target_id=-7))

    def test_registered_active_finite_child_keeps_absolute_timer(self):
        fight = self.f.f.fight
        fight.actors[self.f.actor.id] = self.f.actor
        self.f.actor.team = 0
        fight.phase = "active"
        context = self.context()
        self.assertTrue(context.retained)
        self.assertIsNotNone(context.timer)
        self.assertEqual(context.timer.actor_id, self.f.actor.id)
        self.assertEqual(context.timer.phase, "start")
        self.assertGreater(context.timer.expiration_round, self.f.actor.turn_count)

    def test_delayed_constructor_effect_remains_unsupported(self):
        self.effect["native_timing_definition"]["ryH"] = 1
        with self.f.scope(), self.assertRaisesRegex(ValueError, "verified queue"):
            self.context()

    def test_forged_state_container_remains_rejected(self):
        with self.f.scope(), self.assertRaises(ValueError):
            self.context(replace(self.f.f.invocation, state_uid=123456))


if __name__ == "__main__":
    unittest.main()
