"""Actual card response to El Universo's additional half-Racha payload."""
import os
import struct
import unittest

import test_ecaflip_summon_pipeline as summons


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipUniversePipelineTests(unittest.TestCase):
    fixture = summons.EcaflipSummonPipelineTests.fixture
    draw = summons.EcaflipSummonPipelineTests.draw

    def test_universe_adds_half_native_card_streak_without_bypassing_cap(self):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )

        observed = {}
        for universe in (False, True):
            character, monster, fight, deck, rng = self.draw(
                7944, (8000,) if universe else ()
            )
            _, adapter = server_runtime(
                character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
            )
            uid = 7944
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
            self.assertTrue(candidates["eligible"], candidates)
            cell = candidates["eligible"][0]["target"]
            tx = prepare_server_spell(
                struct.pack(">qqiih", 7, uid, *cell),
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
            observed[universe] = sum(
                s.level
                for s in tx.fight.actors[7].state_ledger.entries
                if s.reference == 3683
            )
            self.assertLessEqual(observed[universe], 100)
        # Successful card359822 applies8044level7;371347 supplies the
        # alternative half (integer3): parent371346 selects first success,
        # so this replaces371348's base7. Disabled dice+50 stays disabled.
        self.assertEqual(observed, {False: 7, True: 3})
