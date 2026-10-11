"""Assimilation reward through actual hostile lethal damage, with baseline."""
import unittest
from unittest.mock import patch
import test_xelor_runtime_pipeline as helpers


class XelorAssimilationLethalRuntimeTests(unittest.TestCase):
    def test_assimilation_rewards_actual_enemy_defeat_after_real_wp_payment(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        helper = helpers.XelorRuntimePipelineTests()
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = helper.fixture(
                    passives=(7196,) if enabled else (), actives=(754, 775)
                )
                paid = helper.cast(data, 775, data[2].actors[-7].position)
                data = helper.adopt(data, paid.fight)
                self.assertGreater(data[2].actors[-7].hp, 0)
                before = data[2].actors[7].effect_stats[4]
                maximum = data[2].actors[7].effect_maxima[4]
                self.assertLess(before, maximum)
                trace = []
                execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = execute(dispatcher, invocation, **kwargs)
                    if invocation.reference in (314319, 314320):
                        trace.append(
                            (
                                invocation.reference,
                                invocation.caster_id,
                                invocation.target_id,
                                result,
                            )
                        )
                    return result

                with patch.object(EffectDispatcher, "execute", observe):
                    tx = helper.cast(
                        data, 754, data[2].actors[-7].position, action_id=20
                    )
                self.assertEqual(tx.fight.actors[-7].hp, 0, trace)
                rewarded = any(ref == 314320 and ok for ref, _, _, ok in trace)
                self.assertEqual(rewarded, enabled, trace)
                self.assertEqual(
                    tx.fight.actors[7].effect_stats[4],
                    min(maximum, before + 2) if enabled else before,
                    trace,
                )
