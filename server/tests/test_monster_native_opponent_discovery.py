"""Conservative native target companion discovery without combat mutation."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_pending_scenarios import (
    discover_native_opponent_recipes,
    required_native_target_identity,
)


class NativeOpponentDiscoveryTests(unittest.TestCase):
    def test_positive_breed_uses_actual_descriptor_endpoints(self):
        rows = [dict(ref=4152, min_level=120, max_level=125)]
        result = discover_native_opponent_recipes(
            'IsBreedId("target", 4152)', rows, {"4152": []}
        )
        self.assertEqual([row["opponent"]["level"] for row in result], [120, 125])
        self.assertTrue(all(row["opponent"]["reference"] == 4152 for row in result))

    def test_state_requires_actual_initial_profile_membership(self):
        rows = [
            dict(ref=1, min_level=2, max_level=2),
            dict(ref=2, min_level=2, max_level=2),
        ]
        result = discover_native_opponent_recipes(
            'HasState(7318, "target")', rows, {"1": [7318, -1, 1], "2": []}
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["required_opponent_states"], [7318])
        self.assertEqual(result[0]["opponent"]["reference"], 1)

    def test_not_or_nested_comparison_cannot_supply_identity(self):
        for criterion in (
            'not IsBreedId("target", 4152)',
            'IsBreedId("target", 4152) or IsEnnemy()',
            'IsBreedId("target", 4152) == False',
            'HasState(7318, "caster")',
            'IsBreedId("target", 4152) and not IsDead("target")',
        ):
            self.assertIsNone(required_native_target_identity(criterion), criterion)

    def test_conflicting_breeds_and_missing_or_invalid_profiles_rejected(self):
        self.assertIsNone(
            required_native_target_identity(
                'IsBreedId("target", 1) and IsBreedId("target", 2)'
            )
        )
        rows = [dict(ref=1, min_level=1, max_level=1)]
        for profiles in ({}, {"1": [7318]}, {"1": [7318, 0, 1]}):
            self.assertEqual(
                discover_native_opponent_recipes(
                    'HasState(7318, "target")', rows, profiles
                ),
                [],
            )

    def test_bounds_are_strict(self):
        with self.assertRaises(ValueError):
            discover_native_opponent_recipes(
                'IsBreedId("target", 1)', [], {}, limit=True
            )
