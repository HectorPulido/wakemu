"""Lethal Ecaflip damage commits even when its subsequent heal has no living target."""
import os
import random
import struct
import unittest

import test_combat_spell_transaction as native_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipLethalHealingPipelineTests(unittest.TestCase):
    def test_lethal_lengua_and_zarpas_do_not_roll_back_for_followup_healing(self):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.spells import encode_deck
        from wakfu_server.fight_checkpoint_store import snapshot

        for reference in (2065, 2072):
            with self.subTest(reference=reference):
                (
                    character,
                    monster,
                    fight,
                ) = native_fixture.SpellTransactionTests().native_server_fixture(
                    6,
                    200,
                    native_qi=True,
                    target_hp=1,
                    target_distance=1,
                    variation_seed=17,
                )
                deck = encode_deck((reference,), ())
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
                _, adapter = server_runtime(
                    character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
                )
                uid = (7 << 32) | reference
                candidates = eligible_cast_targets(
                    fight,
                    character,
                    deck,
                    uid,
                    adapter=adapter,
                    line_of_sight=lambda *args: True,
                    limit=128,
                    maximum_eligible=16,
                )
                enemy_cell = fight.actors[-7].position
                self.assertIn(
                    enemy_cell,
                    [row["target"] for row in candidates["eligible"]],
                    candidates,
                )
                before = snapshot(fight)
                tx = prepare_server_spell(
                    struct.pack(">qqiih", 7, uid, *enemy_cell),
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=2,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=rng,
                )
                self.assertEqual(snapshot(fight), before)
                self.assertTrue(any(tx.outcomes))
                self.assertEqual(tx.fight.actors[-7].hp, 0)
                self.assertLess(tx.fight.actors[7].ap, fight.actors[7].ap)
