"""Encounter prerequisites remain declarative and preserve class buff guards."""
import unittest
from types import SimpleNamespace

from monster_class_buff_scenarios import (
    CLASS_BUFF_RECIPES,
    buff_ally,
    encounter_buff_recipe,
    scenario_constructor_references,
)


class MonsterEncounterBuffRecipeTests(unittest.TestCase):
    def test_spirit_recipe_uses_exact_native_constructor_and_owned_buff(self):
        recipe = encounter_buff_recipe(2778, 4019)
        self.assertEqual(recipe["opponent"], dict(reference=4371, level=68, team=1))
        self.assertEqual(recipe["required_opponent_states"], [2324])
        self.assertEqual(
            {key: recipe[key] for key in CLASS_BUFF_RECIPES["ap"]},
            CLASS_BUFF_RECIPES["ap"],
        )
        self.assertEqual(scenario_constructor_references(2778, 4019), (4371,))

    def test_unknown_spell_has_no_inferred_encounter_constructor(self):
        self.assertIsNone(encounter_buff_recipe(2778, 4020))
        self.assertEqual(scenario_constructor_references(5710, 4641), ())

    def test_recipe_mutation_cannot_change_later_native_prerequisites(self):
        recipe = encounter_buff_recipe(2778, 4019)
        recipe["opponent"]["level"] = 1
        recipe["required_opponent_states"].clear()
        fresh = encounter_buff_recipe(2778, 4019)
        self.assertEqual(fresh["opponent"]["level"], 68)
        self.assertEqual(fresh["required_opponent_states"], [2324])

    def test_encounter_metadata_cannot_bypass_canonical_buff_guard(self):
        fight = SimpleNamespace(actors={})
        with self.assertRaisesRegex(ValueError, "verified class buff recipe"):
            buff_ally(
                fight,
                {},
                {},
                b"",
                ally_id=-200,
                recipe=encounter_buff_recipe(2778, 4019),
                line_of_sight=lambda *args: True,
            )
        self.assertEqual(fight.actors, {})
