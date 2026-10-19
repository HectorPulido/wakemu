"""Paid spell754 AP selection and kill-refund behavior through native execution."""
import copy
import random
import unittest
from unittest.mock import patch

import test_xelor_runtime_pipeline as helpers


class XelorHandRemainingAPTests(unittest.TestCase):
    def _native_jalato_fixture(
        self, helper, *, level=200, passives=(), actives=(754,), target_distance=3
    ):
        original = helpers.native_fixture.fixture

        def jalato(*args, **kwargs):
            args = list(args)
            origin = tuple(args[4])
            target = (origin[0] + target_distance, origin[1], origin[2])
            args[2] = target
            args[3] = helpers.bounded_arena(
                helpers.map_geometry(1134), origin, [target], radius=12
            )
            kwargs.update(monster_reference=1, monster_level=8)
            return original(*args, **kwargs)

        with patch.object(helpers.native_fixture, "fixture", jalato):
            return helper.fixture(level=level, passives=passives, actives=actives)

    def _trial(self, source, ap):
        helper = helpers.XelorRuntimePipelineTests()
        character, monster, fight, deck, rng = source
        private = copy.deepcopy(fight)
        actor = private.actors[7]
        if actor.ap > ap:
            from wakfu_server.combat.combat_resource_pa_notifications import (
                shift_resource_current,
            )

            shift_resource_current(private, actor, 2, actor.ap - ap, subtract=True)
        elif actor.ap < ap:
            raise AssertionError(
                "fixture lacks enough native PA for the requested case"
            )
        trial_rng = random.Random()
        trial_rng.setstate(rng.getstate())
        return helper.adopt((character, monster, fight, deck, trial_rng), private)

    def test_paid_hand_spends_available_ap_capped_at_four_on_native_cast_path(self):
        helper = helpers.XelorRuntimePipelineTests()
        source = helper.fixture(level=20, actives=(754,))
        outcomes = {}
        for available in (1, 2, 3, 4, 5, 6):
            with self.subTest(available_ap=available):
                trial = self._trial(source, available)
                before_hp = trial[2].actors[-7].hp
                tx = helper.cast(trial, 754, trial[2].actors[-7].position)
                caster = tx.fight.actors[7]
                target = tx.fight.actors[-7]
                paid = min(available, 4)
                self.assertEqual(caster.ap, available - paid)
                self.assertLess(target.hp, before_hp)
                self.assertGreater(
                    target.hp, 0, "this case must not trigger kill refund"
                )
                self.assertEqual(trial[2].actors[7].ap, available)
                self.assertEqual(trial[2].actors[-7].hp, before_hp)
                outcomes[available] = (paid, before_hp - target.hp)
        self.assertEqual([outcomes[n][0] for n in range(1, 7)], [1, 2, 3, 4, 4, 4])

    def test_lethal_hand_refund_matches_paid_ap_and_is_caster_owned(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        helper = helpers.XelorRuntimePipelineTests()
        source = self._native_jalato_fixture(helper)
        executed = EffectDispatcher.execute
        refund_rows = {}
        for available in (1, 2, 3, 4, 5, 6):
            with self.subTest(available_ap=available):
                trial = self._trial(source, available)
                caster = trial[2].actors[7]
                target = trial[2].actors[-7]
                before_snapshot = copy.deepcopy(trial[2].actors)
                trace = []

                def observe(dispatcher, invocation, **kwargs):
                    result = executed(dispatcher, invocation, **kwargs)
                    if invocation.reference in {
                        314209,
                        314211,
                        314212,
                        412980,
                        412981,
                        412982,
                        412983,
                        412984,
                        412985,
                        412986,
                        412987,
                        412988,
                    }:
                        current = dispatcher.native_retention.fight.actors[7]
                        trace.append(
                            (
                                invocation.reference,
                                invocation.caster_id,
                                invocation.target_id,
                                current.ap,
                                bool(result),
                            )
                        )
                    return result

                with patch.object(EffectDispatcher, "execute", observe):
                    tx = helper.cast(trial, 754, target.position)
                after = tx.fight.actors[7]
                self.assertEqual(tx.fight.actors[-7].hp, 0, trace)
                paid = min(available, 4)
                self.assertEqual(after.ap, available, trace)
                self.assertEqual(caster.ap, available)
                self.assertGreater(
                    target.hp, 0, "native source fight remains unchanged"
                )
                self.assertTrue(trace, "native kill-refund callback should execute")
                self.assertTrue(
                    any(row[1:3] == (7, -7) and row[4] for row in trace), trace
                )
                self.assertEqual(before_snapshot[7].ap, available)
                refund_rows[available] = trace
        self.assertEqual(set(refund_rows), {1, 2, 3, 4, 5, 6})

    def test_failed_hand_cast_rolls_back_paid_ap_damage_and_rng(self):
        helper = helpers.XelorRuntimePipelineTests()
        source = helper.fixture(level=20, actives=(754,))
        trial = self._trial(source, 3)
        fight = trial[2]
        before = helpers.snapshot(fight)
        rng_before = trial[4].getstate()
        with self.assertRaises(ValueError):
            helper.cast(trial, 754, (100, 100, -1))
        self.assertEqual(helpers.snapshot(fight), before)
        self.assertEqual(trial[4].getstate(), rng_before)

    def test_even_dial_hand_passive_refunds_four_after_native_kill(self):
        helper = helpers.XelorRuntimePipelineTests()
        source = self._native_jalato_fixture(
            helper, passives=(5352,), actives=(754,), target_distance=4
        )
        dial = helper.dial(source)
        source = helper.adopt(source, dial.fight)
        actor = source[2].actors[7]
        target = source[2].actors[-7]
        self.assertEqual(helper.states(actor)[6759], 12)
        self.assertEqual(actor.position, (-6, -7, -1))
        self.assertEqual(
            abs(actor.position[0] - target.position[0])
            + abs(actor.position[1] - target.position[1]),
            2,
        )
        self.assertEqual(actor.ap, 4)
        before = helpers.snapshot(source[2])
        hand = helper.cast(source, 754, target.position)
        self.assertEqual(hand.fight.actors[-7].hp, 0)
        self.assertEqual(hand.fight.actors[7].ap, 4)
        self.assertEqual(helpers.snapshot(source[2]), before)
