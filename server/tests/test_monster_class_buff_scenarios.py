"""Buff recipes use actual class ownership and reject synthetic preparation."""
import unittest
from types import SimpleNamespace

from monster_class_buff_scenarios import CLASS_BUFF_RECIPES, buff_ally
from wakfu_server.spells import encode_deck, validate_deck


class MonsterClassBuffScenarioTests(unittest.TestCase):
    def test_recipes_have_native_unlocked_class_decks(self):
        for recipe in CLASS_BUFF_RECIPES.values():
            deck = validate_deck(
                encode_deck([recipe["spell_id"]]),
                recipe["character_breed"],
                recipe["character_level"],
            )
            self.assertEqual(deck["active"], [recipe["spell_id"]])
            self.assertEqual(recipe["spell_level"], recipe["character_level"])

    def test_unknown_recipe_rejects_before_mutating_fight(self):
        fight = SimpleNamespace(actors={})
        with self.assertRaisesRegex(ValueError, "verified class buff recipe"):
            buff_ally(
                fight,
                {},
                {},
                b"",
                ally_id=-200,
                recipe={},
                line_of_sight=lambda *args: True,
            )
        self.assertEqual(fight.actors, {})

    def test_wrong_breed_cannot_borrow_owned_class_buff(self):
        recipe = CLASS_BUFF_RECIPES["ap"]
        with self.assertRaisesRegex(ValueError, "actual unlocked owner"):
            buff_ally(
                SimpleNamespace(actors={}),
                dict(breed=3, level=3),
                {},
                encode_deck([2839]),
                ally_id=-200,
                recipe=recipe,
                line_of_sight=lambda *args: True,
            )

    def test_missing_owned_deck_spell_rejects_before_accessing_actors(self):
        recipe = CLASS_BUFF_RECIPES["ap"]
        with self.assertRaisesRegex(ValueError, "actual owned deck"):
            buff_ally(
                SimpleNamespace(actors={}),
                dict(breed=5, level=3),
                {},
                encode_deck([]),
                ally_id=-200,
                recipe=recipe,
                line_of_sight=lambda *args: True,
            )
