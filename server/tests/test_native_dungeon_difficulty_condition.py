"""Native eJV absent/present and fail-closed instance authority regressions."""
import unittest
from unittest.mock import patch
from wakfu_server.combat.combat_dungeon_difficulty_condition import native_difficulty
from wakfu_server.combat.combat_instance_level_group import InstanceDifficultySnapshot


class NativeDungeonDifficultyTests(unittest.TestCase):
    def test_null_actor_native_minus_one(self):
        self.assertEqual(native_difficulty(8, None, None), -1)

    def test_non_fighter_native_minus_one(self):
        self.assertEqual(native_difficulty(8, {"is_eGj": False}, None), -1)

    def test_actual_empty_optional_is_not_family1100_zero(self):
        snapshot = InstanceDifficultySnapshot(8, None, "fBg.drG.Optional.empty")
        self.assertEqual(native_difficulty(8, {"is_eGj": True}, snapshot), -1)

    def test_actual_gn_preserves_zero_and_signed_integer(self):
        for value in (0, 1, 50, -7, 2147483647):
            snapshot = InstanceDifficultySnapshot(8, value, "fBg.drG.fBf.GN")
            self.assertEqual(native_difficulty(8, {"is_eGj": True}, snapshot), value)

    def test_missing_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            native_difficulty(8, {"is_eGj": True}, None)

    def test_other_actor_snapshot_rejected(self):
        snapshot = InstanceDifficultySnapshot(9, 3, "fBg.drG.fBf.GN")
        with self.assertRaises(ValueError):
            native_difficulty(8, {"is_eGj": True}, snapshot)

    def test_unknown_actor_type_rejected(self):
        for targeting in ({}, {"is_eGj": 1}):
            with self.assertRaises(ValueError):
                native_difficulty(8, targeting, None)

    @patch("wakfu_server.combat.combat_conditions.canonical_aliases", return_value={})
    def test_real_evaluator_uses_query_and_rejects_missing_authority(self, _aliases):
        from wakfu_server.combat.combat_conditions import (
            ConditionContext,
            evaluate_condition,
            UnknownCondition,
        )

        context = ConditionContext({}, dungeon_difficulty_query=lambda: -1)
        self.assertTrue(evaluate_condition("GetDungeonDifficulty() == -1", context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetDungeonDifficulty() == -1", ConditionContext({}))

    @patch("wakfu_server.combat.combat_conditions.canonical_aliases", return_value={})
    def test_real_evaluator_rejects_arguments_and_boolean_gn(self, _aliases):
        from wakfu_server.combat.combat_conditions import (
            ConditionContext,
            evaluate_condition,
            UnknownCondition,
        )

        context = ConditionContext({}, dungeon_difficulty_query=lambda: True)
        for criterion in (
            "GetDungeonDifficulty() == 1",
            "GetDungeonDifficulty(1) == 1",
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(criterion, context)
