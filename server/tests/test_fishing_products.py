"""Native fixed-primary fishing product rules."""
import unittest
from unittest.mock import patch

from wakfu_server import native_catalog
from wakfu_server.fishing_products import resolve, supports_action, supports_stage
from wakfu_server.paths import DATA_ROOT


class FishingProductTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources = {
            row["resource_reference"]: row
            for row in native_catalog.load(DATA_ROOT / "plant-resources.json")
        }

    def _action(self, reference, stage):
        resource = self.resources[reference]
        definition = next(
            row for row in resource["stage_definitions"] if row["stage_id"] == stage
        )
        return next(row for row in definition["actions"] if row["profession_id"] == 75)

    def test_fixed_primary_ignores_native_candidate_list(self):
        action = self._action(369, 2)
        self.assertEqual(8105, action["item_reference"])
        self.assertGreater(len(action["product_references"]), 1)
        self.assertTrue(supports_action(action))

        class NoPolicyRead:
            def execute(self, *_args):
                raise AssertionError("fixed fishing must not read a policy")

        self.assertEqual(8105, resolve(NoPolicyRead(), action))

    def test_native_cvf_one_is_supported_only_with_known_fixed_primary(self):
        action = self._action(563, 2)
        self.assertEqual(1, action["raw_getters"]["cvF"])
        self.assertGreater(action["item_reference"], 0)
        self.assertTrue(supports_action(action))
        self.assertTrue(supports_stage(563, 2))
        self.assertTrue(supports_stage(563, 1))

    def test_empty_stage_one_does_not_create_a_product(self):
        self.assertTrue(supports_stage(369, 1))
        self.assertIsNone(
            next(
                (
                    action
                    for action in self.resources[369]["stage_definitions"][0]["actions"]
                    if action["profession_id"] == 75
                ),
                None,
            )
        )

    def test_candidate_only_and_unknown_primary_products_fail_closed(self):
        candidate_only = dict(self._action(369, 2), item_reference=0)
        with self.assertRaisesRegex(ValueError, "primary product"):
            resolve(None, candidate_only)

        no_stack = dict(self._action(369, 2), item_reference=999999)
        with patch("wakfu_server.fishing_products._stack_rules", return_value={}):
            self.assertFalse(supports_action(no_stack))
            with self.assertRaisesRegex(ValueError, "primary product"):
                resolve(None, no_stack)

    def test_conditional_wrong_profession_and_nonterminal_actions_are_rejected(self):
        action = self._action(369, 2)
        for edit in (
            {"profession_id": 73},
            {"criteria": "native condition"},
            {"raw_getters": {**action["raw_getters"], "cvF": 2}},
        ):
            with self.subTest(edit=edit):
                self.assertFalse(supports_action({**action, **edit}))

    def test_fish_species_with_only_candidate_free_or_empty_actions_do_not_spawn(self):
        # Reference 306 has no fixed primary item and has a separate native gate.
        self.assertFalse(supports_stage(306, 2))
        self.assertFalse(supports_stage(306, 3))
        self.assertFalse(supports_stage(369, 16))


if __name__ == "__main__":
    unittest.main()
