"""Native bomb HP-to-armor and once-per-action AP restoration branches."""
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
class RogueTacticianTrailTests(unittest.TestCase):
    cast = pipeline.RogueRuntimePipelineTests.cast
    los = staticmethod(pipeline.RogueRuntimePipelineTests.los)
    summons = staticmethod(pipeline.RogueRuntimePipelineTests.summons)

    def fixture(self, passives):
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
        )
        deck, rng = encode_deck((6470,), passives), random.Random(17)
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

    def create_bomb(self, data):
        position = data[2].actors[7].position
        data, _ = self.cast(data, 6470, (position[0] + 1, position[1], position[2]))
        bomb = self.summons(data[2], (3795, 3796, 3797))[0]
        return data, bomb

    def test_powder_trail_actual_elemental_constructor_grants_hp_based_armor(self):
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data, bomb = self.create_bomb(self.fixture((7983,) if equipped else ()))
                armor = sum(actor.effect_stats[97] for actor in data[2].actors.values())
                if equipped:
                    self.assertGreater(armor, 0)
                else:
                    self.assertEqual(armor, 0)
                self.assertEqual(bomb.native_summon_source["controller_id"], 7)

    def test_tactician_actual_swap_restores_exactly_one_ap_for_a_ranked_owned_bomb(
        self,
    ):
        for equipped in (False, True):
            with self.subTest(equipped=equipped):
                data, bomb = self.create_bomb(self.fixture((7982,) if equipped else ()))
                ranks = [
                    row.level
                    for row in bomb.state_ledger.entries
                    if row.reference == 7923
                ]
                self.assertTrue(ranks)
                self.assertGreaterEqual(max(ranks), 2)
                before = data[2].actors[7].ap
                data, tx = self.cast(data, 7904, bomb.position, action_id=11)
                self.assertEqual(
                    data[2].actors[7].ap,
                    before - tx.plan["costs"]["ap"] + int(equipped),
                )
