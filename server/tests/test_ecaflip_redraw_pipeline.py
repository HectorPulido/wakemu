"""Actual Ecaflip played-card recovery and empty-pool rollback."""
import os
import struct
import unittest

import test_ecaflip_tarot_pipeline as tarot


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipRedrawPipelineTests(unittest.TestCase):
    fixture = tarot.EcaflipTarotPipelineTests.fixture

    def cast(self, data, reference, cell):
        from wakfu_server.combat_server_spell import prepare_server_spell

        character, monster, fight, deck, rng = data
        return prepare_server_spell(
            struct.pack(
                ">qqiih",
                7,
                ((7 << 32) | reference) if reference == 2079 else reference,
                *cell
            ),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=10,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )

    def test_mala_suerte_recovers_a_played_card_but_not_an_empty_pool(self):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.fight_checkpoint_store import snapshot

        data = self.fixture(seed=7)
        character, monster, fight, deck, rng = data
        before = snapshot(fight)
        with self.assertRaisesRegex(ValueError, "positive remaining probability total"):
            self.cast(data, 2079, fight.actors[7].position)
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(fight.phase, "active")
        reference = min(set(granted_spells(fight, 7)) & set(range(7938, 7951)))
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=10, critical=False, rng=rng
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
        self.assertTrue(candidates["eligible"], candidates)
        played = self.cast(data, reference, candidates["eligible"][0]["target"])
        self.assertNotIn(reference, granted_spells(played.fight, 7))
        replay_data = (character, monster, played.fight, deck, rng)
        recovered = self.cast(replay_data, 2079, played.fight.actors[7].position)
        self.assertIn(reference, granted_spells(recovered.fight, 7))
        # 359506/359710 retire the unplayed hand; 360639 adds the one
        # recovered card. The resulting native counter is base 1 + one card.
        self.assertEqual(
            set(granted_spells(recovered.fight, 7)) & set(range(7938, 7951)),
            {reference},
        )
        self.assertEqual(
            next(
                entry.level
                for entry in recovered.fight.actors[7].state_ledger.entries
                if entry.reference == 7941
            ),
            2,
        )
        self.assertEqual(
            recovered.fight.actors[7].ap,
            played.fight.actors[7].ap - recovered.plan["costs"]["ap"],
        )
        self.assertEqual(recovered.fight.phase, "active")
