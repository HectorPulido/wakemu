"""Integrity checks for the exported native flora/resource catalogs."""

import unittest

from wakfu_server.planting import RESOURCES, SEEDS


class PlantResourceCatalogTests(unittest.TestCase):
    def test_native_resource_catalog_is_complete_and_internally_consistent(self):
        self.assertEqual(len(RESOURCES), 533)
        self.assertEqual(len(set(RESOURCES)), 533)

        action_ids = []
        getter_names = {
            "cvF",
            "cvG",
            "csN",
            "cvK",
            "cvI",
            "cvH",
            "bwX",
            "csR",
            "cmI",
        }
        action_count = 0

        for reference, resource in RESOURCES.items():
            self.assertEqual(resource["resource_reference"], reference)
            declared_stages = set(resource["stages"])
            definitions = resource["stage_definitions"]
            self.assertEqual(
                {stage["stage_id"] for stage in definitions}, declared_stages
            )
            self.assertEqual(len(definitions), len(declared_stages))

            for stage in definitions:
                for action in stage["actions"]:
                    action_count += 1
                    action_ids.append(action["action_id"])
                    self.assertGreater(action["action_id"], 0)
                    self.assertEqual(type(action["profession_id"]), int)
                    self.assertGreaterEqual(action["minimum_level"], 0)
                    self.assertGreaterEqual(action["duration_ms"], 0)
                    self.assertIsInstance(action["product_references"], list)
                    self.assertTrue(
                        all(
                            type(item_id) is int
                            for item_id in action["product_references"]
                        )
                    )
                    self.assertEqual(set(action["raw_getters"]), getter_names)

        self.assertEqual(action_count, 1141)
        self.assertEqual(len(set(action_ids)), 1141)

    def test_cardo_and_ash_seed_actions_resolve_to_catalog_resources(self):
        self.assertEqual(SEEDS[4275]["resource_reference"], 60)
        self.assertEqual(SEEDS[8063]["resource_reference"], 139)
        self.assertIn(60, RESOURCES)
        self.assertIn(139, RESOURCES)

        cardo = RESOURCES[60]
        ash = RESOURCES[139]
        self.assertEqual(cardo["stages"], [1, 2, 3, 4, 16])
        self.assertEqual(ash["stages"], [1, 2, 3, 4, 16])
        self.assertEqual(cardo["kind"], 2)
        self.assertEqual(ash["kind"], 1)


if __name__ == "__main__":
    unittest.main()
