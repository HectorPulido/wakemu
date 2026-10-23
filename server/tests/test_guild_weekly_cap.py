"""The original total-cap setter is shared by rewards and native projection."""
import unittest

from wakfu_server.guild_weekly_cap import effective_cap
from wakfu_server.guild_model import point_limits
from wakfu_server.guild_service import _has_unsettled_holdings
from datetime import datetime, timezone


class GuildWeeklyCapTests(unittest.TestCase):
    def test_native_setter_replaces_total_without_adding_the_default(self):
        self.assertEqual(7500, effective_cap(dict(weekly_point_cap=7500), {}, {}))
        state = dict(native_weekly_point_cap=1500)
        self.assertEqual(
            1500,
            effective_cap(
                dict(weekly_point_cap=7500), dict(weekly_capacity_bonus=100), state
            ),
        )
        policy = dict(
            native_sync_enabled=True,
            weekly_points_limit=7500,
            earned_points_limit=0,
            last_earning_point_week=0,
            economy=dict(progression_enabled=True, weekly_point_cap=7500),
        )
        guild = dict(weekly_points=2400, weekly_capacity_bonus=0)
        state["week"] = "2026-10-19"
        point_limits(
            policy,
            guild,
            economy_record=state,
            now=datetime(2026, 10, 21, tzinfo=timezone.utc),
        )
        self.assertEqual(1500, guild["weekly_points_limit"])
        self.assertEqual(2400, guild["earned_points_limit"])

    def test_typed_cap_is_nonholding_and_malformed_values_remain_blocked(self):
        for value in (1, 1500, 2**31 - 1):
            self.assertFalse(
                _has_unsettled_holdings("economy", dict(native_weekly_point_cap=value))
            )
        for value in (False, 0, -1, 2**31, 1500.0, "1500"):
            with self.subTest(value=value):
                self.assertTrue(
                    _has_unsettled_holdings(
                        "economy", dict(native_weekly_point_cap=value)
                    )
                )
                with self.assertRaises(ValueError):
                    effective_cap({}, {}, dict(native_weekly_point_cap=value))
