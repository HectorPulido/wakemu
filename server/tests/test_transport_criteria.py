import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "transport_criteria_candidate",
    ROOT / "server/wakfu_server/maps/transport_criteria.py",
)
criteria = importlib.util.module_from_spec(spec)
spec.loader.exec_module(criteria)
from wakfu_server.combat_inventory_date_conditions import calendar_milliseconds


class TransportCriteriaTests(unittest.TestCase):
    def setUp(self):
        self.character = {"id": 7, "level": 200}
        self.now = calendar_milliseconds((12, 10, 2026, 0, 0, 0))

    def allowed(self, expression, **kwargs):
        return criteria.evaluate(expression, self.character, now_ms=self.now, **kwargs)

    def test_all_installed_boat_criteria_accredited_without_waiving_false(self):
        catalog = json.loads(
            Path("docs/reports/NATIVE-BOAT-CONTRACTS-20261011.json").read_text()
        )
        for completed, count in (
            (lambda identity: False, 304),
            (lambda identity: True, 354),
        ):
            results = [
                all(
                    [
                        self.allowed(row[key], achievement_complete=completed)
                        for key in ("source_criterion", "destination_criterion")
                    ]
                )
                for row in catalog["routes"]
            ]
            self.assertEqual(sum(results), count)
        self.assertFalse(self.allowed('@("ascenseur.palais.sadida.prive") False@'))

    def test_native_inclusive_date_and_strict_isbefore_boundaries(self):
        expression = "GetDate() >= GetDate(08,09,2026,09,00,00) and GetDate() <= GetDate(03,11,2026,08,59,59)"
        start = calendar_milliseconds((8, 9, 2026, 9, 0, 0))
        end = calendar_milliseconds((3, 11, 2026, 8, 59, 59))
        for now, allowed in (
            (start - 1, False),
            (start, True),
            (end, True),
            (end + 1, False),
        ):
            self.assertEqual(
                criteria.evaluate(expression, self.character, now_ms=now), allowed
            )
        self.assertFalse(
            criteria.evaluate(
                "IsBefore(08,09,2026,09,00,00)", self.character, now_ms=start
            )
        )
        self.assertTrue(
            criteria.evaluate(
                "IsBefore(08,09,2026,09,00,00)", self.character, now_ms=start - 1
            )
        )

    def test_unknown_malformed_missing_authority_fail_closed(self):
        for expression in (
            "True or Evil()",
            "False and Evil()",
            "GetDate(1)",
            "IsAchievementComplete(-1)",
            "GetDate(x=3)",
            "1",
            "GetRealLevel() > True",
            "@broken",
            "GetDate(31,02,2026,00,00,00)",
            "IsAchievementComplete(2192)",
        ):
            with self.subTest(expression=expression), self.assertRaises(
                (ValueError, SyntaxError)
            ):
                self.allowed(expression)
        with self.assertRaises(ValueError):
            self.allowed(
                "IsAchievementComplete(2192)", achievement_complete=lambda identity: 1
            )

    def test_request_clock_and_owned_snapshot_are_cached_and_foreign_owner_rejected(
        self,
    ):
        class Store:
            def clock(self):
                return 1791763200

        with patch(
            "wakfu_server.maps.dungeon_achievement_authority.queries",
            return_value={"IsAchievementComplete": lambda identity: identity == 2192},
        ) as queries:
            allowed = criteria.evaluator(Store(), self.character)
            self.assertTrue(allowed("IsAchievementComplete(2192)", self.character))
            self.assertFalse(allowed("IsAchievementComplete(3907)", self.character))
            queries.assert_called_once_with(unittest.mock.ANY, 7)
            with self.assertRaises(ValueError):
                allowed("IsAchievementComplete(2192)", {"id": 8, "level": 200})
            self.assertEqual(queries.call_count, 1)
