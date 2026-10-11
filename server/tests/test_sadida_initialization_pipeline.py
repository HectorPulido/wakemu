"""Actual Sadida initialization and optional-passive ownership boundaries."""
import os
import random
import unittest

import test_combat_spell_transaction as native_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaInitializationPipelineTests(unittest.TestCase):
    def fixture(self, *, passives=(), seed=17):
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck

        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            10,
            200,
            native_qi=True,
            target_hp=20000,
            variation_seed=17,
        )
        deck = encode_deck(
            (914, 915, 918, 919, 920, 921, 922, 925, 927, 928, 929, 930), passives
        )
        rng = random.Random(seed)
        fight, packets = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        return character, monster, fight, deck, rng, packets

    def test_ready_registers_native_grants_and_preserves_enemy_isolation(self):
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_qi_fight import current_registry

        _, _, fight, _, _, packets = self.fixture()
        self.assertIsNotNone(fight.current)
        self.assertEqual(fight.current.id, 7)
        current_registry(fight)
        self.assertIn(
            7561, {entry.reference for entry in fight.actors[7].state_ledger.entries}
        )
        grants = granted_spells(fight, 7)
        self.assertTrue({911, 926, 8137} <= set(grants), set(grants))
        self.assertFalse(granted_spells(fight, -7))
        self.assertTrue(packets)

    def test_every_optional_passive_initializes_with_owned_bounded_states(self):
        from wakfu_server.spells import available_spells
        from wakfu_server.combat_spell_grant import granted_spells

        references = [
            row["id"]
            for row in available_spells(10, 200)
            if row["breed"] == 10 and row["kind"] == "passive"
        ]
        self.assertEqual(len(references), 20)
        for reference in references:
            with self.subTest(passive=reference):
                _, _, fight, _, _, _ = self.fixture(passives=(reference,))
                self.assertFalse(granted_spells(fight, -7))
                for entry in fight.actors[7].state_ledger.entries:
                    self.assertGreaterEqual(entry.level, 0)
                self.assertEqual(fight.actors[-7].hp, 20000)
