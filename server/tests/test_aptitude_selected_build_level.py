"""Selected build level must govern aptitude validation at read boundaries."""
import unittest
from unittest.mock import patch

from wakfu_server import aptitudes
from wakfu_server.wire import proto_field


class AptitudeSelectedBuildLevelTests(unittest.TestCase):
    def test_explicit_capped_sheet_level_is_accepted(self):
        character = {
            "level": 200,
            "active_build_index": 1,
            "builds": {1: {"sheet": "owned"}},
        }
        blob = proto_field(24, 20)
        with patch("wakfu_server.builds.effective_sheet_level", return_value=20) as cap:
            parsed = aptitudes.validate_owned_sheet(character, blob)
        self.assertEqual(parsed["available"], aptitudes.budgets(20))
        cap.assert_called_once_with(character, 1)
        self.assertEqual(character["level"], 200)

    def test_automatic_sheet_cannot_spend_real_level_budget_on_capped_build(self):
        category = next(iter(aptitudes.CATEGORIES))
        bonus = next(
            b
            for b in aptitudes.CATEGORIES[category]["bonuses"]
            if b in aptitudes.BONUSES
            and (
                aptitudes.BONUSES[b]["maximum"] == 0
                or aptitudes.BONUSES[b]["maximum"] > aptitudes.budgets(20)[category]
            )
        )
        points = aptitudes.budgets(20)[category] + 1
        blob = proto_field(24, (1 << 64) - 1) + proto_field(
            34, proto_field(8, bonus) + proto_field(16, points)
        )
        character = {"level": 200, "builds": {0: {"sheet": "owned"}}}
        with patch("wakfu_server.builds.effective_sheet_level", return_value=20):
            with self.assertRaisesRegex(ValueError, "budget"):
                aptitudes.validate_owned_sheet(character, blob)

    def test_explicit_build_selection_uses_its_cap(self):
        character = {
            "level": 200,
            "active_build_index": 0,
            "builds": {2: {"sheet": "owned"}},
        }
        with patch("wakfu_server.builds.effective_sheet_level", return_value=50) as cap:
            result = aptitudes.validate_owned_sheet(
                character, proto_field(24, 50), build_index=2
            )
        self.assertEqual(result["available"], aptitudes.budgets(50))
        cap.assert_called_once_with(character, 2)
