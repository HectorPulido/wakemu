"""Resilience armor replaces Wakfu recovery in actual Celestial Gift."""
import os
import unittest

import test_combat_eliotrope_runtime as runtime
import eliotrope_allied_fixture as allied


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropeResilienceRuntimeTests(allied.EliotropeAlliedFixture, unittest.TestCase):
    fixture = runtime.EliotropeRuntimeTests.fixture
    cast = runtime.EliotropeRuntimeTests.cast
    place_portal = runtime.EliotropeRuntimeTests.place_portal
    next_owned_turn = runtime.EliotropeRuntimeTests.next_owned_turn

    def test_actual_gift_does_not_invent_legacy_self_only_armor(self):
        observations = {}
        for enabled in (False, True):
            data = self.allied_fixture(passives=(4686, 4690) if enabled else (4686,))
            before = data[2].actors[8]
            armor = before.effect_stats.get(97, 0)
            hp = before.effect_maxima[1] + before.effect_maxima[92]
            tx = self.allied_cast(data, 7813)
            actor = tx.fight.actors[8]
            observations[enabled] = (actor.effect_stats.get(97, 0) - armor, hp)
            self.assertEqual(actor.id, 8)
            self.assertIn(
                (3671, 1, 7),
                {
                    (state.reference, state.level, state.caster_id)
                    for state in actor.state_ledger.entries
                },
            )
            self.assertNotIn(
                3671,
                {state.reference for state in tx.fight.actors[7].state_ledger.entries},
            )
            self.assertEqual(
                tx.fight.actors[7].effect_stats.get(97, 0),
                data[2].actors[7].effect_stats.get(97, 0),
            )
        self.assertEqual(observations[False][0], 0, observations)
        self.assertEqual(observations[False][1], observations[True][1], observations)
        # Native397196/eYs mode1 selects maximumHP+VIRTUAL_HP, multiplies0.1,
        # rounds positive half-up, then397197 applies that level as armor1013.
        self.assertEqual(
            observations[True][0], (observations[True][1] + 5) // 10, observations
        )
        self.assertGreater(observations[True][0], 0, observations)
