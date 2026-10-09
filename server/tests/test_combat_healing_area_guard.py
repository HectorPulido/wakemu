"""Actual retained Feca area HP absence follows eXs.C/c without fighter stats."""
import random
import unittest
from test_combat_area_timed_expiration import AreaTimedExpirationTests
from wakfu_server.combat_healing_handler import NativeHealingHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.fight_checkpoint_store import snapshot


class HealingAreaGuardTests(unittest.TestCase):
    def test_registered_area_no_hp_preserves_lifecycle_without_heal_notification(self):
        fight = AreaTimedExpirationTests().fixture()
        target = next(iter(fight.native_effect_areas))
        packets = []
        phases = []

        class Events:
            def phase(self, effect, invocation, **data):
                phases.append((data["channel"], data["value"]))

        def forbidden_context(*args):
            raise AssertionError("Area must not acquire fighter healing context")

        handler = NativeHealingHandler(
            fight,
            packets,
            action_id=3,
            allocate_uid=lambda: 900,
            context=forbidden_context,
            rng=random.Random(1).random,
        )
        handler.event_lifecycle = Events()
        effect = dict(effect_class=1084, parameters=[50, 1])
        invocation = EffectInvocation(386023, 200, 7, target, fight.actors[7].position)
        before = snapshot(fight)
        invocation = handler.prepare(effect, {}, invocation)
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(phases, [(1, 0), (2, 0), (3, 0), (4, 0)])
        self.assertFalse(packets)
        self.assertEqual(snapshot(fight), before)
