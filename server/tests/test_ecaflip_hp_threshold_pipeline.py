"""Actual incoming damage crosses La Fortuna's native half-HP threshold."""
import os
import random
import unittest

import test_combat_spell_transaction as native_fixture
import test_aniripsa_grant_summon_pipeline as lifecycle


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipHpThresholdPipelineTests(unittest.TestCase):
    end_current_turn = lifecycle.AniripsaGrantSummonPipelineTests.end_current_turn

    def test_fortune_requires_actual_crossing_from_above_half_hp(self):
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.spells import encode_deck

        observed = {}
        for passive, crossing in ((True, True), (False, True), (True, False)):
            with self.subTest(passive=passive, crossing=crossing):
                (
                    character,
                    monster,
                    fight,
                ) = native_fixture.SpellTransactionTests().native_server_fixture(
                    6,
                    200,
                    native_qi=True,
                    target_hp=20000,
                    target_distance=1,
                    variation_seed=17,
                )
                deck = encode_deck((), (7956,) if passive else ())
                rng = random.Random(7)
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
                data = character, monster, fight, deck, rng
                for _ in range(20):
                    if fight.current.id == -7:
                        break
                    self.end_current_turn(fight, data)
                self.assertEqual(fight.current.id, -7)
                caster = fight.actors[7]
                set_hp_raw_current(
                    caster, caster.max_hp // 2 + 1 if crossing else caster.max_hp // 4
                )
                hp = caster.hp
                tx = prepare_npc_spell(
                    fight,
                    dict(
                        type="cast",
                        spellId=7962,
                        level=1,
                        targetId=7,
                        target=list(caster.position),
                    ),
                    character,
                    {-7: monster},
                    deck,
                    action_id=20,
                    rng=rng,
                )
                after = tx.fight.actors[7]
                self.assertLess(after.hp, hp)
                self.assertLess(after.hp, after.max_hp / 2)
                racha = sum(
                    s.level for s in after.state_ledger.entries if s.reference == 3683
                )
                observed[passive, crossing] = racha
        # Compare the native crossing reward against the same real damage
        # baseline: innate6892 root359218 (end-turn1002) supplies
        # 8044level20 through369987. Preserve that independent reward.
        self.assertEqual(observed[True, True] - observed[False, True], 50)
        self.assertEqual(observed[True, False], observed[False, True])
