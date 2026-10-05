"""Real Feca6992 starter through ordinary initialization, without guard bypass."""
import unittest
from random import Random
import test_combat_spell_transaction as fixtures
from wakfu_server.combat_server_spell import prepare_server_initialization
from wakfu_server.spells import encode_deck
from wakfu_server.fight_checkpoint_store import snapshot


class FecaStartTests(unittest.TestCase):
    def test_passive_start_resolves_global_round_zero_and_keeps_source_unchanged(self):
        (
            character,
            monster,
            fight,
        ) = fixtures.SpellTransactionTests().native_server_fixture(1, 25)
        deck = encode_deck((), [6992])
        before = snapshot(fight)
        started, packets = prepare_server_initialization(
            character,
            {monster["id"]: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        self.assertTrue(started.native_start_event_delivered)
        self.assertEqual(started.native_table_turn, 0)
        self.assertIn(
            9315, {entry.reference for entry in started.actors[7].state_ledger.entries}
        )
        self.assertTrue(packets)
        self.assertEqual(snapshot(fight), before)
        stable = snapshot(started)
        with self.assertRaises(ValueError):
            prepare_server_initialization(
                character,
                {monster["id"]: monster},
                started,
                3,
                deck,
                action_id=2,
                rng=Random(7),
                fight_start=True,
            )
        self.assertEqual(snapshot(started), stable)
