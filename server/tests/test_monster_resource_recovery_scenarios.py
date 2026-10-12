"""Observed deficits select actual preparations without inventing resources."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_class_buff_scenarios import CLASS_BUFF_RECIPES, resource_recovery_recipes


class MonsterResourceRecoveryScenarioTests(unittest.TestCase):
    def test_ap_and_mp_select_existing_owned_class_preparations(self):
        result = resource_recovery_recipes(dict(deficits=dict(mp=1, ap=3)))
        self.assertEqual(result, [CLASS_BUFF_RECIPES["ap"], CLASS_BUFF_RECIPES["mp"]])
        result[0]["spell_id"] = 99
        self.assertEqual(CLASS_BUFF_RECIPES["ap"]["spell_id"], 2839)

    def test_wp_or_unknown_deficit_does_not_suggest_unsupported_grants(self):
        for deficits in (dict(wp=1), dict(ap=2, wp=1), dict(other=1)):
            with self.subTest(deficits=deficits):
                self.assertEqual(resource_recovery_recipes(dict(deficits=deficits)), [])

    def test_missing_and_malformed_observations_are_rejected(self):
        for diagnostic in (
            None,
            {},
            dict(deficits={}),
            dict(deficits=dict(ap=True)),
            dict(deficits=dict(mp=0)),
            dict(deficits=dict(ap=-1)),
        ):
            with self.subTest(diagnostic=diagnostic):
                self.assertEqual(resource_recovery_recipes(diagnostic), [])


if __name__ == "__main__":
    unittest.main()
