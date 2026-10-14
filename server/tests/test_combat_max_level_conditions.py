"""Native maximum-level roster filters and configuration remain distinct."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.combat_max_level_conditions import (
    fighters_max_level,
    player_max_level,
)
from wakfu_server.combat_system_conditions import fresh_system_configuration


class NativeMaxLevelTests(unittest.TestCase):
    def test_player_union_and_native_exclusion_filters(self):
        rows = [
            (0, True, frozenset(), 20),
            (5, True, frozenset(), 30),
            (1, True, frozenset(), 200),
            (0, False, frozenset(), 80),
            (0, True, frozenset({114}), 90),
        ]
        self.assertEqual(fighters_max_level(rows), 30)
        self.assertEqual(fighters_max_level(rows, "player", False), 80)
        self.assertEqual(fighters_max_level(rows, "monster"), 200)

    def test_monster_is_exact_type_one_and_empty_is_zero(self):
        self.assertEqual(fighters_max_level([(2, True, frozenset(), 99)], "monster"), 0)
        self.assertEqual(fighters_max_level([]), 0)
        self.assertEqual(
            fighters_max_level([(5, True, frozenset(), 42)], "unknown"), 42
        )

    def test_config_default_and_override_not_roster_maximum(self):
        fight = SimpleNamespace(
            native_system_configuration=fresh_system_configuration()
        )
        self.assertEqual(player_max_level(fight), 245)
        fight.native_system_configuration["overrides"]["player.level.cap"] = 200
        self.assertEqual(player_max_level(fight), 200)
        fight.native_system_configuration["overrides"]["player.level.cap"] = True
        with self.assertRaises(ValueError):
            player_max_level(fight)

    @patch("wakfu_server.combat_conditions.canonical_aliases", return_value={})
    def test_numeric_predicates_use_attested_callbacks(self, _aliases):
        context = ConditionContext(
            {},
            fighters_max_level_query=lambda kind, active: 30,
            player_max_level_query=lambda: 245,
        )
        self.assertTrue(
            evaluate_condition(
                'GetFightersMaxLevel("player") < GetPlayerMaxLevel()', context
            )
        )
        self.assertTrue(
            evaluate_condition('GetFightersMaxLevel("monster", false) == 30', context)
        )

    @patch("wakfu_server.combat_conditions.canonical_aliases", return_value={})
    def test_missing_authority_and_invalid_signature_reject(self, _aliases):
        for criterion in (
            "GetFightersMaxLevel() > 0",
            "GetPlayerMaxLevel() > 0",
            "GetFightersMaxLevel(3) > 0",
            "GetPlayerMaxLevel(1) > 0",
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(criterion, ConditionContext({}))

    def test_unknown_selected_level_and_membership_reject(self):
        with self.assertRaises(ValueError):
            fighters_max_level([(0, None, frozenset(), 20)])
        with self.assertRaises(ValueError):
            fighters_max_level([(0, True, frozenset(), None)])
