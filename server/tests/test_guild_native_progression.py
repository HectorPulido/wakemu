"""Original guild costs/gates plus explicit nonnegative point rounding policy."""
from datetime import datetime, timezone
import unittest

from wakfu_server import guild_progression as progression
from wakfu_server.guild_model import point_limits
from wakfu_server.achievements.rewards import validate


class GuildNativeProgressionTests(unittest.TestCase):
    def test_native_catalog_and_four_paid_compartments(self):
        source = progression.catalog()
        self.assertEqual(len(source["bonuses"]), 78)
        self.assertEqual(len(progression.supported_bonuses()), 78)
        for identity, level, cost, hours, compartment in (
            (11, 4, 3000, 16, 0),
            (33, 6, 5000, 48, 1),
            (50, 8, 10000, 96, 2),
            (69, 10, 20000, 168, 3),
        ):
            with self.subTest(identity=identity):
                row = progression.supported_bonuses()[str(identity)]
                self.assertEqual(
                    (
                        row["minimum_guild_level"],
                        row["cost"],
                        row["learning_duration_ms"],
                    ),
                    (level, cost, hours * 3600000),
                )
                self.assertEqual(
                    row["effect"],
                    dict(kind="unlock_compartment", value=compartment, duration_ms=-1),
                )
        self.assertEqual(
            progression.supported_bonuses()["1"]["effect"]["kind"], "member_effect"
        )
        for identity in ("72", "73"):
            descriptor = progression.supported_bonuses()[identity]
            self.assertEqual(descriptor["activation_mode"], "manual")
            self.assertEqual(descriptor["renewal_mode"], "paid_relearn")
            self.assertEqual(descriptor["effect"]["duration_ms"], 21600000)
        self.assertEqual(
            progression.supported_bonuses()["42"]["effect"],
            dict(kind="weekly_point_limit", value=1500, duration_ms=-1),
        )
        self.assertEqual(
            progression.supported_bonuses()["84"]["effect"],
            dict(kind="unlock_haven_world", value=84, duration_ms=-1),
        )

    def test_composed_policy_uses_exact_native_quest_amounts_and_preserves_storage(
        self,
    ):
        base = dict(
            enabled=True,
            management_enabled=True,
            native_sync_enabled=True,
            native_request_opcodes=[15877],
            owner_id_semantics="account",
            chest={"enabled": True},
            economy={"treasury_enabled": True},
        )
        policy = progression.progression_policy(base, enabled=True)
        self.assertEqual(
            policy["economy"]["point_sources"],
            {
                "native_achievement:1389": 15,
                "native_achievement:1390": 15,
                "native_achievement:1391": 20,
            },
        )
        self.assertEqual(policy["economy"]["weekly_point_cap"], 7500)
        self.assertTrue(policy["economy"]["treasury_enabled"])
        self.assertTrue(policy["chest"]["enabled"])
        self.assertEqual(set(policy["native_request_opcodes"]), {15877, 15613, 14447})
        self.assertNotIn("progression_enabled", base["economy"])

    def test_explicit_floor_policy_and_native_reward_type12_bounds(self):
        for amount, expected in ((15, 16), (20, 22), (25, 27), (100, 110)):
            self.assertEqual(
                progression.point_reward(amount, {"points_earned_factor": 1.1}),
                expected,
            )
        self.assertEqual(progression.point_reward(15, {}), 15)
        for factor in (True, 1.2, -1, float("nan")):
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                progression.point_reward(15, {"points_earned_factor": factor})
        self.assertEqual(validate({"d": 2479, "aeV": 12, "ckl": [15]}), (12, (15,)))
        for parameters in ([], [0], [-1], [True], [15, 20]):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                validate({"d": 2479, "aeV": 12, "ckl": parameters})

    def test_stored_week_projection_resets_visible_earned_without_hydration_write(self):
        policy = dict(
            native_sync_enabled=True,
            primary_identity_only=False,
            weekly_points_limit=0,
            earned_points_limit=0,
            last_earning_point_week=0,
            economy={"progression_enabled": True, "weekly_point_cap": 7500},
        )
        guild = dict(weekly_points=321, weekly_capacity_bonus=0)
        point_limits(
            policy,
            guild,
            economy_record={"week": "2026-10-19"},
            now=datetime(2026, 10, 21, tzinfo=timezone.utc),
        )
        self.assertEqual(
            (
                guild["weekly_points_limit"],
                guild["earned_points_limit"],
                guild["last_earning_point_week"],
            ),
            (7500, 321, 43),
        )
        point_limits(
            policy,
            guild,
            economy_record={"week": "2026-10-19"},
            now=datetime(2026, 10, 26, tzinfo=timezone.utc),
        )
        self.assertEqual(guild["earned_points_limit"], 0)
        self.assertEqual(guild["weekly_points"], 321)


class GuildCriterionProgressionTests(unittest.TestCase):
    def test_all_eight_original_criterion_bonuses_activate_identity_without_stat_writes(
        self,
    ):
        from unittest.mock import Mock
        from wakfu_server.guild_economy import _apply_effect

        descriptors = progression.supported_bonuses()
        actual = [
            row
            for row in progression.catalog()["bonuses"]
            if row["effect_type"] == "CRITERION_BONUS"
        ]
        self.assertEqual(len(actual), 8)
        for row in actual:
            with self.subTest(identity=row["id"]):
                effect = descriptors[str(row["id"])]["effect"]
                self.assertEqual(
                    effect,
                    dict(kind="criterion_bonus", value=row["id"], duration_ms=-1),
                )
                db = Mock()
                _apply_effect(db, {"id": 1}, effect)
                db.execute.assert_not_called()


class GuildLearnedModifierHoldingsTests(unittest.TestCase):
    def test_native_learned_modifiers_do_not_become_refundable_custody(self):
        from wakfu_server.guild_service import _has_unsettled_holdings

        record = dict(
            learning_duration_factor=0.9,
            maximum_simultaneous_learning=2,
            points_earned_factor=1.1,
            week="2026-10-19",
            bonuses={},
        )
        self.assertFalse(_has_unsettled_holdings("economy", record))
        for extra in (
            {"kamas": 1},
            {"unknown_entitlement": 1},
            {"points_earned_factor": True},
            {"learning_duration_factor": 2},
        ):
            self.assertTrue(_has_unsettled_holdings("economy", dict(record, **extra)))
