"""Owned Ecaflip flea healing, critical and Pulgacion split branches."""
import os
import random
import struct
import unittest

import test_combat_aptitude_healing_runtime as allied


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipFleaPipelineTests(unittest.TestCase):
    fixture = allied.AptitudeHealingRuntimeTests.fixture
    setUpClass = allied.AptitudeHealingRuntimeTests.__dict__["setUpClass"]

    def test_pulga_arcito_splits_healing_into_native_fleas_only_with_passive(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot

        results = {}
        for critical in (False, True):
            for passive in (False, True):
                with self.subTest(critical=critical, passive=passive):
                    fight, characters, monster, decks = self.fixture(
                        active_spells=(2067,),
                        passive_spells=(2062,) if passive else (),
                        caster_breed=6,
                        level=200,
                        caster_aptitudes=(),
                        injury=600,
                    )
                    before = snapshot(fight)
                    hp = fight.actors[8].hp
                    tx = prepare_server_spell(
                        struct.pack(
                            ">qqiih", 7, (7 << 32) | 2067, *fight.actors[8].position
                        ),
                        characters[7],
                        {-7: monster},
                        fight,
                        3,
                        decks[7],
                        action_id=10,
                        line_of_sight=lambda *args: True,
                        critical=critical,
                        rng=random.Random(7),
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                    healed = tx.fight.actors[8].hp - hp
                    fleas = sum(
                        entry.level
                        for entry in tx.fight.actors[8].state_ledger.entries
                        if entry.reference == 3697
                    )
                    self.assertGreater(healed, 0)
                    self.assertEqual(snapshot(fight), before)
                    self.assertEqual(tx.fight.actors[-7].hp, fight.actors[-7].hp)
                    self.assertEqual(
                        tx.fight.actors[7].ap,
                        fight.actors[7].ap - tx.plan["costs"]["ap"],
                    )
                    if passive:
                        self.assertGreater(fleas, 0)
                    else:
                        self.assertEqual(fleas, 0)
                    results[critical, passive] = (healed, fleas)
        for critical in (False, True):
            normal, _ = results[critical, False]
            split, fleas = results[critical, True]
            self.assertLess(split, normal)
            # Fleas store the native raw half-base, not the mastery-scaled
            # immediate HP gain. Native level-200 samples are 26 and 32.
            self.assertEqual(fleas, 32 if critical else 26)
            self.assertLessEqual(abs(normal - 2 * split), 1)
        self.assertGreater(results[True, False][0], results[False, False][0])
