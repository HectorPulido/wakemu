"""Summons cannot reduce XP or supply group/level bonuses to either team."""
import copy
import unittest

from wakfu_server.reward_policy import xp_amount


class SummonXpTests(unittest.TestCase):
    def context(self):
        return dict(
            winner_team=0,
            challenge_percent=0,
            star_percent=0,
            winners=[
                dict(level=7, player=True, eligible=True, character_id=65, wisdom=0)
            ],
            losers=[dict(level=4, monster_reference=2)],
        )

    def xp(self, context, rate=100000):
        return xp_amount(
            character_id=65,
            context=context,
            group_xp=433,
            xp_rate_bp=rate,
            conquest_rate_bp=10000,
        )

    def test_reported_level7_vs_level4_gives_same_xp_with_or_without_summon(self):
        baseline = self.context()
        summoned = copy.deepcopy(baseline)
        summoned["winners"].insert(
            0, dict(level=7, player=False, eligible=False, character_id=None, wisdom=0)
        )
        self.assertEqual(self.xp(baseline), 5532)
        self.assertEqual(self.xp(summoned), 5532)
        self.assertEqual(self.xp(summoned, 10000), 553)

    def test_summon_count_and_level_cannot_change_reward(self):
        baseline = self.context()
        for level in (1, 7, 245, 32767):
            for number in (1, 3, 8):
                with self.subTest(level=level, number=number):
                    ctx = copy.deepcopy(baseline)
                    ctx["winners"].extend(
                        dict(
                            level=level,
                            player=False,
                            eligible=False,
                            character_id=None,
                            wisdom=0,
                        )
                        for _ in range(number)
                    )
                    self.assertEqual(self.xp(ctx), self.xp(baseline))

    def test_enemy_summon_levels_cannot_create_bonus_or_penalty(self):
        baseline = self.context()
        ctx = copy.deepcopy(baseline)
        ctx["losers"].extend(
            dict(level=32767, monster_reference=None) for _ in range(5)
        )
        self.assertEqual(self.xp(ctx), self.xp(baseline))

    def test_real_second_player_still_participates_in_group_calculation(self):
        baseline = self.context()
        grouped = copy.deepcopy(baseline)
        grouped["winners"].append(
            dict(level=7, player=True, eligible=True, character_id=66, wisdom=0)
        )
        self.assertNotEqual(self.xp(grouped), self.xp(baseline))
        with_summon = copy.deepcopy(grouped)
        with_summon["winners"].append(
            dict(level=245, player=False, eligible=False, character_id=None, wisdom=0)
        )
        self.assertEqual(self.xp(with_summon), self.xp(grouped))
