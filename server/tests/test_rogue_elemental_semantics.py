"""Actual owned Rogue elemental attacks against a registered living target."""
import os
import random
import unittest

import test_combat_spell_transaction as native_fixture
import test_rogue_runtime_pipeline as pipeline
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_turn_start,
)
from wakfu_server.spells import encode_deck


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RogueElementalSemanticsTests(unittest.TestCase):
    cast = pipeline.RogueRuntimePipelineTests.cast
    los = staticmethod(pipeline.RogueRuntimePipelineTests.los)

    def fixture(self, reference):
        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            13,
            200,
            native_qi=True,
            full_health=True,
            target_hp=20000,
            target_distance=3,
            variation_seed=17,
            target_position=(-6, -5, -1) if reference == 6466 else None,
        )
        deck, rng = encode_deck((reference,), ()), random.Random(17)
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
        fight, _ = prepare_server_turn_start(
            character,
            {-7: monster},
            fight,
            deck,
            actor_id=fight.current.id,
            action_id=2,
            rng=rng,
            area_callbacks=True,
        )
        return character, monster, fight, deck, rng

    def test_fifteen_original_elemental_spells_affect_a_living_registered_enemy(self):
        for reference in (*range(6463, 6477), 6478):
            with self.subTest(reference=reference):
                data = self.fixture(reference)
                before_hp = data[2].actors[-7].hp
                before_ap = data[2].actors[7].ap
                data, tx = self.cast(data, reference, data[2].actors[-7].position)
                if reference == 6464:
                    # Native359411/370354 attach6876; no direct damage is authored.
                    self.assertEqual(data[2].actors[-7].hp, before_hp)
                    self.assertIn(
                        6876,
                        {
                            row.reference
                            for row in data[2].actors[-7].state_ledger.entries
                        },
                    )
                else:
                    self.assertLess(data[2].actors[-7].hp, before_hp)
                self.assertLess(data[2].actors[7].ap, before_ap)
                self.assertTrue(any(tx.outcomes))

    def test_explicit_native_fixture_position_rejects_missing_terrain(self):
        with self.assertRaises(ValueError):
            native_fixture.SpellTransactionTests().native_server_fixture(
                13,
                200,
                native_qi=True,
                full_health=True,
                target_position=(-999999, -999999, -1),
                variation_seed=17,
            )
