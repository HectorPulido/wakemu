"""Advanced Mechanics is a reverse-channel outgoing damage tradeoff."""
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerAdvancedMechanicsRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast

    def test_advanced_mechanics_reduces_actual_owned_direct_damage(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        samples = {}
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = self.fixture((6943,) if enabled else (), actives=(6902,))
                trace = []
                execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = execute(dispatcher, invocation, **kwargs)
                    trace.append((invocation.reference, result))
                    return result

                with patch.object(EffectDispatcher, "execute", observe):
                    tx = self.cast(data, 6902, target=data[2].actors[-7].position)
                damage = data[2].actors[-7].hp - tx.fight.actors[-7].hp
                self.assertGreater(damage, 0, trace)
                samples[enabled] = damage
                if enabled:
                    self.assertIn((344029, True), trace)
                else:
                    self.assertFalse(any(ref == 344029 for ref, _ in trace))
        self.assertLess(samples[True], samples[False], samples)
