"""Captured native affiliation cannot be replaced by mutable owner facts."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_area_affiliation import area_affiliation


class AreaCapturedAffiliationTests(unittest.TestCase):
    def test_captured_affiliation_survives_owner_change_and_retirement(self):
        fight = SimpleNamespace(actors={7: SimpleNamespace(team=1)})
        row = dict(
            owner_id=7,
            native_fight_affiliation=0,
            native_fight_affiliation_source="faV.j(PV).bcM",
        )
        self.assertEqual(area_affiliation(fight, row), 0)
        fight.actors.clear()
        self.assertEqual(area_affiliation(fight, row), 0)

    def test_invalid_supplied_capture_never_falls_back_to_owner(self):
        fight = SimpleNamespace(actors={7: SimpleNamespace(team=0)})
        for value in (None, True, 128, -129, "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                area_affiliation(
                    fight,
                    dict(
                        owner_id=7,
                        native_fight_affiliation=value,
                        native_fight_affiliation_source="faV.j(PV).bcM",
                    ),
                )
        with self.assertRaises(ValueError):
            area_affiliation(fight, dict(owner_id=7, native_fight_affiliation=0))

    def test_legacy_absent_capture_requires_actual_owner_affiliation(self):
        fight = SimpleNamespace(actors={7: SimpleNamespace(team=0)})
        self.assertEqual(area_affiliation(fight, dict(owner_id=7)), 0)
        with self.assertRaises(ValueError):
            area_affiliation(fight, dict(owner_id=8))


if __name__ == "__main__":
    unittest.main()
