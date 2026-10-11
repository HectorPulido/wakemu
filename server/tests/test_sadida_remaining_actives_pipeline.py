"""Sadida active spells that require native doll, ally or armor contexts."""
import os
import unittest

import test_sadida_grant_pipeline as grants
import test_sadida_doll_actions_pipeline as dolls
import test_aniripsa_grant_summon_pipeline as turns


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaRemainingActivesPipelineTests(unittest.TestCase):
    fixture = grants.SadidaGrantPipelineTests.fixture
    cast = grants.SadidaGrantPipelineTests.cast

    def test_actual_owned_doll_supplies_sacrifice_and_earthquake_prerequisites(self):
        from wakfu_server.spells import encode_deck
        from wakfu_server.combat_server_spell import prepare_server_initialization
        import test_combat_spell_transaction as native_fixture
        import random

        for reference in (920, 935):
            with self.subTest(reference=reference):
                (
                    character,
                    monster,
                    fight,
                ) = native_fixture.SpellTransactionTests().native_server_fixture(
                    10, 200, native_qi=True, target_hp=20000, variation_seed=17
                )
                deck = encode_deck((925, reference))
                rng = random.Random(17)
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
                data = (character, monster, fight, deck, rng, packets)
                seeded = self.cast(data, 8137)
                data = (*data[:2], seeded.fight, *data[3:])
                cell = next(
                    a["cell"]
                    for a in seeded.fight.native_effect_areas.values()
                    if a["reference"] == 1835
                )
                born = self.cast(data, 925, target=cell, action_id=11)
                data = (*data[:2], born.fight, *data[3:])
                turns.AniripsaGrantSummonPipelineTests().next_player_turn(
                    data[2], data[:5]
                )
                actor = next(
                    a
                    for a in data[2].actors.values()
                    if getattr(a, "native_summon_source", None) and a.hp > 0
                )
                tx = self.cast(
                    data,
                    reference,
                    target=data[2].actors[7].position
                    if reference == 920
                    else actor.position,
                    action_id=20,
                )
                if reference == 920:
                    self.assertEqual(tx.fight.actors[actor.id].hp, 0)
                    self.assertEqual(tx.fight.actors[actor.id].native_obstacle_id, -1)
                else:
                    self.assertTrue(any(tx.outcomes))

    def test_actual_zarza_self_armor_enables_fuerza_naturaleza(self):
        from wakfu_server.spells import encode_deck
        import random
        import test_combat_spell_transaction as native_fixture
        from wakfu_server.combat_server_spell import prepare_server_initialization

        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            10, 200, native_qi=True, target_hp=20000, variation_seed=17
        )
        deck = encode_deck((925, 8139))
        rng = random.Random(17)
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
        data = (character, monster, fight, deck, rng, packets)
        armored = self.cast(data, 925, target=fight.actors[7].position)
        self.assertGreater(armored.fight.actors[7].effect_stats.get(97, 0), 0)
        data = (*data[:2], armored.fight, *data[3:])
        tx = self.cast(data, 8139, action_id=11)
        self.assertIn(
            8224, {s.reference for s in tx.fight.actors[7].state_ledger.entries}
        )
