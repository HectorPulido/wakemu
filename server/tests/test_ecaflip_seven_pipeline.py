"""Six real card plays trigger Siete Fetiche's native streak reward."""
import os
import struct
import unittest

import test_ecaflip_tarot_pipeline as tarot
import test_aniripsa_grant_summon_pipeline as lifecycle


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipSevenPipelineTests(unittest.TestCase):
    fixture = tarot.EcaflipTarotPipelineTests.fixture
    end_current_turn = lifecycle.AniripsaGrantSummonPipelineTests.end_current_turn

    def test_six_actual_cards_grant_one_hundred_streak(self):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells

        data = self.fixture(seed=7, passives=(7999,))
        character, monster, fight, deck, rng = data
        played = 0
        for turn in range(12):
            for _ in range(3):
                cards = [
                    reference
                    for reference in granted_spells(fight, 7)
                    if 7938 <= reference <= 7950
                ]
                progressed = False
                for reference in cards:
                    _, adapter = server_runtime(
                        character,
                        {-7: monster},
                        deck,
                        action_id=10 + played,
                        critical=False,
                        rng=rng,
                    )
                    candidates = eligible_cast_targets(
                        fight,
                        character,
                        deck,
                        reference,
                        adapter=adapter,
                        line_of_sight=lambda *args: True,
                        limit=128,
                        maximum_eligible=1,
                    )
                    if not candidates["eligible"]:
                        continue
                    fight = prepare_server_spell(
                        struct.pack(
                            ">qqiih", 7, reference, *candidates["eligible"][0]["target"]
                        ),
                        character,
                        {-7: monster},
                        fight,
                        3,
                        deck,
                        action_id=10 + played,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=rng,
                    ).fight
                    played += 1
                    progressed = True
                    racha = sum(
                        s.level
                        for s in fight.actors[7].state_ledger.entries
                        if s.reference == 3683
                    )
                    if played < 6:
                        self.assertLess(racha, 100)
                        self.assertEqual(
                            sum(
                                s.level
                                for s in fight.actors[7].state_ledger.entries
                                if s.reference == 8047
                            ),
                            played,
                        )
                    else:
                        self.assertEqual(played, 6)
                        self.assertEqual(racha, 100)
                        return
                    break
                if not progressed:
                    break
            for _ in range(20):
                self.end_current_turn(fight, data)
                if fight.current.id == 7:
                    break
            self.assertEqual(fight.current.id, 7)
        self.fail(f"Only {played} actual card plays completed in bounded turns")
