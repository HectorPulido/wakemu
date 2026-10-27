import unittest
from wakfu_server.spell_audit import states_catalog
from wakfu_server.combat_state_ledger import StateLedger, StateTimeline
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
)


class StateLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = states_catalog()

    def test_accumulation_replaces_instance_and_keeps_actual_source(self):
        ledger = StateLedger(-7)
        ledger.apply(self.catalog, 3442, 200, caster_id=7, uid=101)
        change = ledger.apply(self.catalog, 3442, 200, caster_id=8, uid=102)
        self.assertEqual(change.applied.level, 400)
        self.assertEqual([entry.uid for entry in change.removed], [101])
        self.assertEqual(ledger.entries, (change.applied,))
        context = ConditionContext(
            {
                "caster": StateLedger(8).condition_actor(),
                "target": ledger.condition_actor(),
            }
        )
        self.assertTrue(evaluate_condition('HasStateFromUser(3442, "target")', context))
        saturated = ledger.apply(self.catalog, 3442, 1, caster_id=7, uid=103)
        self.assertIsNone(saturated.applied)
        self.assertEqual(ledger.entries[0].uid, 102)

    def test_replacement_callback_sees_old_carrier_and_preserves_nested_entries(self):
        ledger = StateLedger(7)
        old = ledger.apply(self.catalog, 3442, 20, caster_id=7, uid=101).applied
        calls = []

        def before_replace(entry):
            self.assertIs(entry, old)
            self.assertEqual(ledger.entries, (old,))
            calls.append(entry.uid)
            ledger.apply(
                self.catalog,
                3425,
                20,
                caster_id=7,
                uid=103,
                applying_effect_has_delay=True,
            )
            ledger.remove(entry.uid)

        change = ledger.apply(
            self.catalog, 3442, 20, caster_id=8, uid=102, before_replace=before_replace
        )
        self.assertEqual(calls, [101])
        self.assertEqual([entry.uid for entry in ledger.entries], [103, 102])
        self.assertEqual(change.removed, (old,))

    def test_instant_state_is_returned_for_execution_but_not_retained(self):
        ledger = StateLedger(7)
        change = ledger.apply(
            self.catalog,
            3425,
            20,
            caster_id=7,
            uid=104,
            applying_effect_has_delay=False,
        )
        self.assertEqual(change.applied.duration, 0)
        self.assertTrue(change.applied.effect_ids)
        self.assertEqual(ledger.entries, ())

    def test_zero_duration_requires_delay_context_and_can_be_retained(self):
        ledger = StateLedger(7)
        with self.assertRaisesRegex(ValueError, "delay"):
            ledger.apply(self.catalog, 3425, 20, caster_id=7, uid=108)
        self.assertEqual(ledger.entries, ())
        change = ledger.apply(
            self.catalog, 3425, 20, caster_id=7, uid=108, applying_effect_has_delay=True
        )
        self.assertTrue(change.applied.retained)
        self.assertEqual(ledger.entries, (change.applied,))

    def test_failed_application_leaves_collection_intact(self):
        ledger = StateLedger(7)
        ledger.apply(self.catalog, 3442, 20, caster_id=7, uid=105)
        before = ledger.entries
        for options in [
            dict(reference=999999, level=20, caster_id=7, uid=106),
            dict(reference=3442, level=-32769, caster_id=7, uid=106),
            dict(reference=3442, level=20, caster_id=7, uid=105),
        ]:
            with self.assertRaises(ValueError):
                ledger.apply(self.catalog, **options)
            self.assertEqual(ledger.entries, before)

    def test_timed_state_keeps_native_clock_and_explicit_removal(self):
        ledger = StateLedger(-7)
        change = ledger.apply(self.catalog, 8913, 30, caster_id=7, uid=107)
        self.assertEqual(change.applied.duration, 1)
        self.assertEqual(change.applied.clock_actor, "caster")
        self.assertFalse(change.applied.tick_at_turn_end)
        self.assertEqual(ledger.remove(107), change.applied)
        self.assertEqual(ledger.entries, ())
        self.assertIsNone(ledger.remove(107))

    def test_expiry_uses_caster_clock_not_target_or_other_fighter(self):
        ledger = StateLedger(-7)
        change = ledger.apply(
            self.catalog,
            8913,
            30,
            caster_id=7,
            uid=109,
            timeline=StateTimeline(1, 7, 0, 0, "active"),
        )
        self.assertEqual(change.applied.timer.expiration_round, 2)
        for actor_id, round_number, phase in [
            (-7, 2, "start"),
            (7, 1, "start"),
            (7, 2, "end"),
        ]:
            self.assertEqual(
                ledger.expire(
                    actor_id=actor_id, round_number=round_number, phase=phase
                ),
                (),
            )
        self.assertEqual(
            ledger.expire(actor_id=7, round_number=2, phase="start"), (change.applied,)
        )
        self.assertEqual(ledger.entries, ())

    def test_permanent_state_survives_round_cleanup(self):
        ledger = StateLedger(7)
        ledger.apply(
            self.catalog,
            3442,
            20,
            caster_id=7,
            uid=110,
            timeline=StateTimeline(1, 7, 0, 0, "active"),
        )
        self.assertEqual(
            ledger.expire(
                actor_id=7, round_number=100, phase="start", round_cleanup=True
            ),
            (),
        )
        self.assertEqual(ledger.entries[0].uid, 110)


if __name__ == "__main__":
    unittest.main()
