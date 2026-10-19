"""Verify Python XP against independently exported original Wakfu methods."""
import json
import math
from pathlib import Path
import unittest

from wakfu_server.wakfu_xp import monster_base_xp, intended_fights, level_factor
from wakfu_server.character_levels import XP_BY_LEVEL, MAX_CHARACTER_LEVEL


class NativeWakfuXpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(
            (Path(__file__).parent / "fixtures/native_wakfu_xp_model.json").read_text()
        )

    def test_all_native_monster_bases_and_fight_counts(self):
        for row in self.fixture["levels"]:
            with self.subTest(level=row["level"]):
                self.assertEqual(monster_base_xp(row["level"]), row["monster_base_xp"])
                self.assertAlmostEqual(
                    intended_fights(row["level"]), row["intended_fights"], places=10
                )

    def test_single_progression_curve_matches_original_and_base_model_through245(self):
        self.assertEqual(MAX_CHARACTER_LEVEL, 245)
        total = 0.0
        for row in self.fixture["levels"]:
            level = row["level"]
            with self.subTest(level=level):
                self.assertEqual(XP_BY_LEVEL[level], row["threshold"])
                self.assertEqual(math.floor(total), row["threshold"])
            total += monster_base_xp(level) * max(1, intended_fights(level))

    def test_high_native_npc_levels_saturate_without_float_overflow(self):
        for row in self.fixture["high_npc_levels"]:
            with self.subTest(level=row["level"]):
                self.assertEqual(monster_base_xp(row["level"]), row["monster_base_xp"])

    def test_extreme_level_gaps_cannot_cycle_to_bonus(self):
        self.assertEqual(level_factor(1, 32767), 0)
        self.assertAlmostEqual(level_factor(245, 1), 0.3)
        self.assertEqual(level_factor(50, 50), 1)

    def test_reported_case_uses_literal_community_level_factor(self):
        self.assertEqual(monster_base_xp(4), 433)
        self.assertEqual(int(433 * level_factor(7, 4) * 1.3), 553)
