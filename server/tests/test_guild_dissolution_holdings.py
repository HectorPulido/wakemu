"""Dissolution settles actual holdings rather than historical bookkeeping."""
import unittest

from wakfu_server.characters.guild_service import _has_unsettled_holdings


class GuildDissolutionHoldingsTests(unittest.TestCase):
    def test_zero_treasury_and_progression_history_can_be_dissolved(self):
        self.assertFalse(
            _has_unsettled_holdings(
                "economy",
                {
                    "kamas": 0,
                    "week": "2026-10-05",
                    "bonuses": {"4": {"active": True, "purchased_at_ms": 1}},
                },
            )
        )

    def test_money_unknown_services_and_unknown_fields_require_settlement(self):
        for service, record in (
            ("economy", {"kamas": 1}),
            ("economy", {"kamas": -1}),
            ("economy", {"kamas": False}),
            ("economy", {"chest_items": [1]}),
            ("chest", {"items": [1]}),
            ("economy", []),
        ):
            with self.subTest(service=service, record=record):
                self.assertTrue(_has_unsettled_holdings(service, record))

    def test_empty_service_records_are_not_holdings(self):
        self.assertFalse(_has_unsettled_holdings("economy", {}))
        self.assertFalse(_has_unsettled_holdings("chest", {}))
