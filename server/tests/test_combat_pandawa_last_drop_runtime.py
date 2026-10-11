"""Actual Tipsy removal publishes2223 and restores WP or grants native HP-scaled armor through Last Drop."""
import os
import unittest
import test_combat_pandawa_runtime as fixture_module


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaLastDropRuntimeTests(unittest.TestCase):
    fixture = fixture_module.PandawaRuntimeTests.fixture
    cast = fixture_module.PandawaRuntimeTests.cast

    def test_last_drop_replaces_real_wp_restoration_with_hp_scaled_armor(self):
        from unittest.mock import patch
        from wakfu_server.combat_event_replay import NativeEventReplay
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        gains, armor_gains = {}, {}
        for passive in (None, 8598):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                # Real barrel and Tipsy actions create a WP deficit, rather
                # than modifying current resources to force the comparison.
                barrel = self.cast(fixture, 4718)
                fixture = (*fixture[:2], barrel.fight, *fixture[3:])
                tipsy = self.cast(
                    fixture, 8592, target=fixture[2].actors[-7].position, action_id=3
                )
                fixture = (*fixture[:2], tipsy.fight, *fixture[3:])
                self.assertIn(
                    6107,
                    {
                        entry.reference
                        for entry in fixture[2].actors[-7].state_ledger.entries
                    },
                )
                before = fixture[2].actors[7].effect_stats[4]
                before_armor = fixture[2].actors[7].effect_stats.get(97, 0)
                delivered, executed = [], []
                replay = NativeEventReplay.__call__
                execute = EffectDispatcher.execute

                def observe_event(runtime, source, **kwargs):
                    if 2223 in source.event_ids:
                        delivered.append(
                            (
                                source.effect_action_id,
                                source.uid,
                                source.caster_id,
                                source.target_id,
                            )
                        )
                    return replay(runtime, source, **kwargs)

                def observe_effect(dispatcher, invocation, **kwargs):
                    result = execute(dispatcher, invocation, **kwargs)
                    if invocation.reference == 417331:
                        executed.append(result)
                    return result

                with patch.object(
                    NativeEventReplay, "__call__", observe_event
                ), patch.object(EffectDispatcher, "execute", observe_effect):
                    removed = self.cast(
                        fixture,
                        4702,
                        target=fixture[2].actors[-7].position,
                        action_id=4,
                    )
                self.assertTrue(
                    any(
                        family == 321 and uid > 0 and caster == 7 and target == -7
                        for family, uid, caster, target in delivered
                    ),
                    delivered,
                )
                self.assertIn(True, executed)

                self.assertNotIn(
                    6107,
                    {
                        entry.reference
                        for entry in removed.fight.actors[-7].state_ledger.entries
                    },
                )
                gains[passive] = removed.fight.actors[7].effect_stats[4] - before
                armor_gains[passive] = (
                    removed.fight.actors[7].effect_stats.get(97, 0) - before_armor
                )
                if passive == 8598:
                    self.assertEqual(
                        armor_gains[passive],
                        int(removed.fight.actors[7].max_hp * 0.05 + 0.5),
                    )
        self.assertEqual(gains[None], 1)
        self.assertEqual(gains[8598], 0)
        self.assertEqual(armor_gains[None], 0)
        self.assertGreater(armor_gains[8598], 0)
