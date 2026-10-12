"""Supportive witnesses use real constructor identities and actor positions."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_pending_scenarios import (
    additional_native_actor_targets,
    native_ally_recipe,
)


class NativeSupportiveAllySearchTests(unittest.TestCase):
    def test_supportive_recipe_preserves_native_reference_and_level(self):
        recipe = native_ally_recipe(3, 14, dict(tags=["buff"]))
        self.assertEqual(recipe["opponent"], dict(reference=3, level=14, team=1))
        self.assertEqual(recipe["kind"], "native_opponent")
        self.assertNotIn("states", recipe)
        self.assertNotIn("resources", recipe)

    def test_damage_only_does_not_add_unnecessary_companion(self):
        self.assertIsNone(native_ally_recipe(3, 14, dict(tags=["damage", "debuff"])))

    def test_targets_include_living_actual_ally_without_duplicates_or_dead_actor(self):
        def actor(position, hp=30):
            return SimpleNamespace(position=position, hp=hp)

        fight = SimpleNamespace(
            actors={
                7: actor((1, 0, 0)),
                -200: actor((0, 0, 0)),
                -201: actor((0, 1, 0)),
                -202: actor((0, -1, 0), 0),
            }
        )
        existing = [((1, 0, 0), 7), ((0, 0, 0), -200)]
        self.assertEqual(
            additional_native_actor_targets(fight, existing), [((0, 1, 0), -201)]
        )
        self.assertEqual(len(existing), 2)


if __name__ == "__main__":
    unittest.main()
