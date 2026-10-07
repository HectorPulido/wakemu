import json
from pathlib import Path
import unittest


class MountFeedingCatalogTests(unittest.TestCase):
    def test_native_effect_classification_for_reported_and_xp_foods(self):
        catalog = json.loads(
            (Path(__file__).parents[1] / "protocol" / "mount-models.json").read_text()
        )
        self.assertEqual(catalog["count"], 40)
        self.assertEqual(len(catalog["models"]), 40)
        for model in catalog["models"]:
            food = model["food"]
            heals = {
                row["reference"]: row["health_per_item"]
                for row in food["healing_food_values"]
            }
            xp = set(food["xp_item_refs"])
            self.assertEqual(set(food["meal_item_refs"]), set(heals))
            self.assertTrue(xp)
            self.assertTrue(
                all(type(amount) is int and amount > 0 for amount in heals.values())
            )
            self.assertTrue(xp.isdisjoint(heals))
            self.assertTrue(
                xp.issubset(
                    {
                        row["reference"]
                        for row in food["xp_food_flags"]
                        if row["enabled"] is True
                    }
                )
            )
            self.assertTrue(
                {12284, 13358, 18377}.issubset(heals)
                or not ({12284, 13358, 18377} & set(food["meal_item_refs"]))
            )
            self.assertEqual(
                {ref for ref in (12284, 13358, 18377) if ref in heals},
                set(food["meal_item_refs"]) & {12284, 13358, 18377},
            )
            for reference, value in ((12284, 1), (13358, 1), (18377, 20)):
                if reference in heals:
                    self.assertEqual(heals[reference], value)
                self.assertNotIn(reference, xp)
            self.assertIn(18378, xp)


if __name__ == "__main__":
    unittest.main()
