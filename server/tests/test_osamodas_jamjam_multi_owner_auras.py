"""Actual Jamjam aura activation and source-specific retirement across owners."""
import os
import unittest
from unittest.mock import patch

import test_osamodas_jamjam_action_consequences as jamjam_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
@patch.dict(
    os.environ, {"WAKFU_NATIVE_GRANTED_CAST": "1", "WAKFU_NATIVE_AREA_CALLBACKS": "1"}
)
class JamjamMultiOwnerAuraTests(unittest.TestCase):
    def areas(self, fight, reference):
        return {
            uid: row
            for uid, row in getattr(fight, "native_effect_areas", {}).items()
            if row["reference"] == reference
        }

    def test_two_actual_lunar_sources_damage_once_each_and_retire_independently(self):
        observed = []
        for owners in ((7,), (7, 8)):
            with self.subTest(owners=owners):
                fixture = jamjam_fixture.JamjamActionConsequencesTests()
                characters, decks, fight = fixture.fixture()
                sources = {}
                casters = {}
                for owner in owners:
                    fight, jamjam = fixture.summon(characters, decks, fight, owner)
                    old = set(self.areas(fight, 1689))
                    fight = fixture.cast(
                        characters,
                        decks,
                        fight,
                        jamjam,
                        7352,
                        fight.actors[owner].position,
                    )
                    fresh = set(self.areas(fight, 1689)) - old
                    self.assertEqual(len(fresh), 1)
                    sources[owner] = fresh.pop()
                    casters[owner] = jamjam
                before_hp = fight.actors[9].hp
                fight = fixture.turn(characters, decks, fight, 9)
                damage = before_hp - fight.actors[9].hp
                self.assertGreater(damage, 0)
                self.assertTrue(
                    any(
                        entry.reference == 7144
                        for entry in fight.actors[9].state_ledger.entries
                    )
                )
                observed.append(damage)
                if len(owners) == 2:
                    self.assertEqual(len(self.areas(fight, 1689)), 2)
                    fight = fixture.turn(characters, decks, fight, casters[7])
                    self.assertNotIn(sources[7], self.areas(fight, 1689))
                    self.assertIn(sources[8], self.areas(fight, 1689))
                    self.assertTrue(
                        any(
                            entry.reference == 7151
                            for entry in fight.actors[8].state_ledger.entries
                        )
                    )
        self.assertEqual(len(observed), 2)
        self.assertEqual(observed[1], observed[0] * 2)

    def test_real_solar_healing_resistance_and_two_owner_retirement(self):
        fixture = jamjam_fixture.JamjamActionConsequencesTests()
        characters, decks, fight = fixture.fixture()
        fight = fixture.turn(characters, decks, fight, 9)
        # Injure recipients through two ordinary legal attacks, never HP writes.
        fight = fixture.cast(
            characters, decks, fight, 9, 6261, fight.actors[7].position
        )
        fight = fixture.cast(
            characters, decks, fight, 9, 6266, fight.actors[8].position
        )
        injured = fight.actors[8].hp
        self.assertLess(injured, fight.actors[8].max_hp)
        fight, jamjam_a = fixture.summon(characters, decks, fight, 7)
        fight = fixture.move(
            characters, decks, fight, jamjam_a, [(-2, -18, 0), (-1, -18, 0)]
        )
        before_resistance = fight.actors[8].effect_stats[27]
        before_range = fight.actors[8].effect_stats[11]
        before_final_damage = fight.actors[8].effect_stats[48]
        fight = fixture.cast(
            characters, decks, fight, jamjam_a, 7353, fight.actors[7].position
        )
        a_ids = set(self.areas(fight, 1690))
        self.assertEqual(len(a_ids), 1)
        fight = fixture.turn(characters, decks, fight, 8)
        self.assertGreater(fight.actors[8].hp, injured)
        self.assertLessEqual(fight.actors[8].hp, fight.actors[8].max_hp)
        self.assertEqual(fight.actors[8].effect_stats[27], before_resistance + 50)
        self.assertEqual(fight.actors[8].effect_stats[11], before_range + 2)
        self.assertEqual(fight.actors[8].effect_stats[48], before_final_damage + 15)
        self.assertTrue(
            any(
                entry.reference == 7145
                for entry in fight.actors[8].state_ledger.entries
            )
        )
        fight, jamjam_b = fixture.summon(characters, decks, fight, 8)
        fight = fixture.move(
            characters, decks, fight, jamjam_b, [(-2, -16, 0), (-1, -16, 0)]
        )
        before_ids = set(self.areas(fight, 1690))
        fight = fixture.cast(
            characters, decks, fight, jamjam_b, 7353, fight.actors[8].position
        )
        b_ids = set(self.areas(fight, 1690)) - before_ids
        self.assertEqual(len(b_ids), 1)
        self.assertEqual(len(self.areas(fight, 1690)), 2)
        fight = fixture.turn(characters, decks, fight, jamjam_a)
        self.assertTrue(a_ids.isdisjoint(self.areas(fight, 1690)))
        self.assertTrue(b_ids <= set(self.areas(fight, 1690)))
        self.assertTrue(
            any(
                entry.reference == 7152
                for entry in fight.actors[8].state_ledger.entries
            )
        )
