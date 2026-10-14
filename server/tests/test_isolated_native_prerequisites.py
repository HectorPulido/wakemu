"""Strict disposable prerequisite recipe inputs; actual handlers tested warm."""
import unittest
from isolated_native_prerequisites import validate_recipe


class IsolatedNativePrerequisiteTests(unittest.TestCase):
    def test_declarative_states_area_and_budget_are_copied(self):
        recipe = {
            "states": [{"state_id": 7134, "level": 1}],
            "areas": [
                {
                    "effect_id": 114048,
                    "level": 1,
                    "cell": [-7, -7, -1],
                    "area_reference": 684,
                }
            ],
        }
        result = validate_recipe(recipe)
        result["states"][0]["level"] = 2
        self.assertEqual(recipe["states"][0]["level"], 1)
        self.assertNotIn("wp_budget", result)

    def test_unknown_and_unbounded_inputs_rejected(self):
        for recipe in [
            {"native_flags": True},
            {"wp_budget": 3},
            {"wp_budget": -1},
            {"wp_budget": 100000},
            {"states": [{"state_id": 0, "level": 1}]},
            {"areas": [{"effect_id": 114048, "level": 1, "cell": [1, 2]}]},
        ]:
            with self.subTest(recipe=recipe), self.assertRaises(ValueError):
                validate_recipe(recipe)

    def test_absent_state_fixture_is_explicit_and_rejects_resource_grants(self):
        self.assertEqual(
            validate_recipe({"absent_states": [852]})["absent_states"], [852]
        )
        for recipe in (
            {"absent_states": [0]},
            {"absent_states": ["852"]},
            {"absent_states": [852], "wp_budget": 1},
        ):
            with self.subTest(recipe=recipe), self.assertRaises(ValueError):
                validate_recipe(recipe)

    def test_state_recipient_role_is_explicit(self):
        recipe = {"states": [{"state_id": 2999, "level": 4, "role": "target"}]}
        self.assertEqual(validate_recipe(recipe), recipe)
        with self.assertRaises(ValueError):
            validate_recipe(
                {"states": [{"state_id": 2999, "level": 4, "role": "invented"}]}
            )
