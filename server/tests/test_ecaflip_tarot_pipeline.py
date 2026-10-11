"""Ecaflip native hand creation and weighted draw ownership invariants."""
import os
import random
import unittest

import test_combat_spell_transaction as native_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipTarotPipelineTests(unittest.TestCase):
    def fixture(self, *, seed=7, passives=(), level=200):
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck

        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            6,
            level,
            native_qi=True,
            target_hp=20000,
            variation_seed=17,
        )
        deck = encode_deck(
            (2041, 2042, 2045, 2047, 2060, 2061, 2065, 2067, 2073, 2078, 2079, 7225),
            passives,
        )
        rng = random.Random(seed)
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        return character, monster, fight, deck, rng

    def hand(self, fight):
        from wakfu_server.combat_spell_grant import granted_spells

        entries = fight.actors[7].state_ledger.entries
        cards = [entry for entry in entries if 7961 <= entry.reference <= 7973]
        counter = [entry for entry in entries if entry.reference == 7941]
        self.assertEqual(len(counter), 1)
        self.assertEqual(len({entry.reference for entry in cards}), len(cards))
        self.assertLessEqual(len(cards), 3)
        self.assertEqual(counter[0].level, 1 + len(cards))
        grants = granted_spells(fight, 7)
        self.assertIn(7227, grants)
        for entry in cards:
            self.assertIn(entry.reference - 23, grants)
        self.assertEqual(
            {reference for reference in grants if 7938 <= reference <= 7950},
            {entry.reference - 23 for entry in cards},
        )
        return cards

    def test_actual_ready_draws_distinct_owned_cards_with_native_hand_cap(self):
        observed = set()
        for seed in (0, 1, 2, 3, 7, 17):
            with self.subTest(seed=seed):
                _, _, fight, _, _ = self.fixture(seed=seed)
                self.assertEqual(fight.current.id, 7)
                cards = self.hand(fight)
                self.assertEqual(len(cards), 3)
                observed.update(entry.reference for entry in cards)
        self.assertGreater(len(observed), 3)

    def test_optional_passives_initialize_without_duplicate_or_foreign_grants(self):
        from wakfu_server.spells import available_spells

        passives = [
            row["id"]
            for row in available_spells(6, 200)
            if row["breed"] == 6 and row["kind"] == "passive"
        ]
        self.assertEqual(len(passives), 20)
        for reference in passives:
            with self.subTest(passive=reference):
                _, _, fight, _, _ = self.fixture(passives=(reference,))
                cards = self.hand(fight)
                if reference == 5251:
                    self.assertEqual(len(cards), 1)
                else:
                    self.assertEqual(len(cards), 3)
