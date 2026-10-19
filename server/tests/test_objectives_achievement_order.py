"""Achievement presentation ordering does not change eligibility or progress."""
import unittest

from wakfu_server.objectives.player_views import (
    achievement_difficulty,
    achievement_sort_key,
)


class AchievementOrderTests(unittest.TestCase):
    def card(self, key, level, state="available", target=1):
        return dict(
            key=key,
            title=key,
            difficulty_level=level,
            state=state,
            objectives=[dict(target=target)],
        )

    def test_completed_first_then_native_dungeon_difficulty(self):
        cards = [
            self.card("gobball", 28),
            self.card("endgame", 200),
            self.card("cats", 10),
            self.card("finished", 150, "completed"),
        ]
        self.assertEqual(
            [card["key"] for card in sorted(cards, key=achievement_sort_key)],
            ["finished", "cats", "gobball", "endgame"],
        )

    def test_completed_achievements_also_follow_difficulty(self):
        cards = [
            self.card("higher", 100, "completed"),
            self.card("lower", 50, "completed"),
        ]
        self.assertEqual(sorted(cards, key=achievement_sort_key)[0]["key"], "lower")

    def test_milestones_sort_by_level_then_distinct_count(self):
        cards = [
            self.card("three", 200, target=3),
            self.card("two", 200, target=2),
            self.card("one", 200),
            self.card("fifty", 50),
        ]
        self.assertEqual(
            [c["key"] for c in sorted(cards, key=achievement_sort_key)],
            ["fifty", "one", "two", "three"],
        )

    def test_difficulty_uses_hardest_required_dungeon_not_numeric_id(self):
        definition = dict(objectives=[dict(filters=dict(dungeon_id=[99, 1]))])
        self.assertEqual(achievement_difficulty(definition, {99: 10, 1: 28}), 28)

    def test_difficulty_uses_milestone_threshold_not_player_reward_level(self):
        definition = dict(objectives=[dict(filters=dict(minimum_level=150))])
        self.assertEqual(achievement_difficulty(definition, {}), 150)

    def test_unknown_levels_follow_known_levels_with_stable_title_order(self):
        cards = [self.card("unknown", None), self.card("known", 200)]
        self.assertEqual(sorted(cards, key=achievement_sort_key)[0]["key"], "known")
        self.assertIsNone(
            achievement_difficulty(dict(objectives=[dict(filters={})]), {})
        )
