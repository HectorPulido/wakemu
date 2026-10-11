"""Actual native clock payment, Suspension fallback and explicit release."""
import unittest
from unittest.mock import patch
from wakfu_server.combat_effect_dispatch import EffectDispatcher
import test_xelor_runtime_pipeline as helpers


class XelorClockResourceRuntimeTests(unittest.TestCase):
    def test_plain_paid_wp_wraps_hour_without_suspension_fallback(self):
        helper = helpers.XelorRuntimePipelineTests()
        trace = []
        execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (413004, 413005):
                trace.append((invocation.reference, result))
            return result

        with patch.object(EffectDispatcher, "execute", observe):
            data = helper.fixture()
            dial = helper.dial(data)
            before = dial.fight.actors[7]
            trace.clear()
            paid = helper.cast(
                helper.adopt(data, dial.fight),
                775,
                dial.fight.actors[-7].position,
                action_id=21,
            )
        after = paid.fight.actors[7]
        self.assertEqual(
            (after.ap, after.effect_stats[4]),
            (before.ap - 1, before.effect_stats[4] - 1),
        )
        self.assertEqual(helper.states(after)[6759], 1)
        # Native314228 has limit1/count-success: successful413004 skips413005.
        self.assertEqual(trace, [(413004, True)])
        self.assertNotIn(9245, helper.states(after))
        self.assertEqual(helper.states(before)[6759], 12)

    def test_actual_paid_wp_advances_current_hour_and_keeps_one_suspension_receipt(
        self,
    ):
        helper = helpers.XelorRuntimePipelineTests()
        trace = []
        stage = "initialization"
        execute = EffectDispatcher.execute
        observed_refs = {413004, 413005, 413416, 412999, 413421, 413424, 413418, 413419}

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in observed_refs:
                actor = dispatcher.native_retention.fight.actors[7]
                trace.append(
                    (
                        stage,
                        invocation.reference,
                        result,
                        helper.states(actor).get(9245, 0),
                    )
                )
            return result

        with patch.object(EffectDispatcher, "execute", observe):
            data = helper.fixture(actives=(751, 775, 754))
            dial = helper.dial(data)
            data = helper.next_owned_turn(helper.adopt(data, dial.fight))
            mechanism = next(a for a in data[2].actors.values() if a.id not in (7, -7))
            stage = "first_751"
            suspended = helper.cast(data, 751, mechanism.position, action_id=51)
            data = helper.adopt(data, suspended.fight)
            self.assertEqual(helper.states(data[2].actors[7])[9245], 2)
            before = data[2].actors[7]
            stage = "paid_775"
            paid = helper.cast(data, 775, data[2].actors[-7].position, action_id=52)
            actor = paid.fight.actors[7]
            self.assertEqual(
                (actor.ap, actor.effect_stats[4]),
                (before.ap - 1, before.effect_stats[4] - 1),
            )
            self.assertEqual(helper.states(actor)[6759], 12)
            self.assertEqual(helper.states(actor)[9245], 3)
            self.assertIn(("paid_775", 413004, False, 2), trace)
            self.assertIn(("paid_775", 413005, True, 3), trace)
            stage = "turn_boundary"
            data = helper.next_owned_turn(helper.adopt(data, paid.fight))
            self.assertEqual(helper.states(data[2].actors[7])[9245], 3)
            self.assertEqual(helper.states(data[2].actors[7])[6759], 12)
            self.assertFalse(any(row[0] == stage and row[1] == 412999 for row in trace))
            stage = "release_751"
            released = helper.cast(data, 751, mechanism.position, action_id=53)
            states = helper.states(released.fight.actors[7])
            self.assertNotIn(9245, states)
            self.assertEqual(states[6759], 3)
            self.assertIn(("release_751", 412999, True, 0), trace)
            self.assertTrue(
                any(
                    row[0] == "release_751" and row[1] == 413421 and row[2]
                    for row in trace
                )
            )
