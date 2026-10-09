"""Actual class initialization -> normal cast -> native post-cast states."""
import os
import random
import struct
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class CastEventRuntimeTests(unittest.TestCase):
    def test_cra_normal_cast_applies_original_post_cast_state_children_atomically(self):
        from tests.test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
        )
        from wakfu_server.spells import encode_deck

        character, creature, fight = SpellTransactionTests().native_server_fixture(
            9, 200, native_qi=True
        )
        deck = encode_deck([4820])
        initialized, _ = prepare_server_initialization(
            character,
            {-7: creature},
            fight,
            3,
            deck,
            action_id=1,
            rng=random.Random(0),
            fight_start=True,
        )
        self.assertTrue(initialized.native_start_event_delivered)
        self.assertTrue(
            any(
                state.reference == 3419
                for state in initialized.actors[7].state_ledger.entries
            )
        )
        before = tuple(initialized.actors[7].state_ledger.entries)
        self.assertFalse(any(state.reference in (7758, 7793) for state in before))
        rng = random.Random(0)
        target = initialized.actors[-7].position
        transaction = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 4820, *target),
            character,
            {-7: creature},
            initialized,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        states = {
            state.reference: state
            for state in transaction.fight.actors[7].state_ledger.entries
        }
        # Native 350554 -> 352071 -> 352072/352074, evaluated normally.
        # Native carriers7758/7793 have duration0: their original children
        # 347094/349856 persist3430/7792 instead of retaining the carriers.
        applied = {
            event["state_id"]: event
            for event in transaction.fight.events
            if event["kind"] == "state_applied"
            and event["sequence"] > initialized.sequence
            and event["actor_id"] == 7
        }
        for reference in (7758, 7793):
            self.assertEqual(applied[reference]["level"], 3)
            self.assertEqual(applied[reference]["duration"], 0)
            self.assertTrue(applied[reference]["instant"])
        self.assertEqual(states[3430].level, 30)
        self.assertEqual(states[7792].level, 30)
        self.assertNotIn(7758, states)
        self.assertNotIn(7793, states)
        self.assertNotIn(7760, states)  # Original HasState(7757) branch is false.
        self.assertEqual(tuple(initialized.actors[7].state_ledger.entries), before)
        self.assertGreater(len(transaction.packets), 2)
        self.assertIsNone(initialized.native_active_spell_id)
        self.assertIsNone(transaction.fight.native_active_spell_id)
