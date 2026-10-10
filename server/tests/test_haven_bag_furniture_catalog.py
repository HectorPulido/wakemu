"""Native furniture mapping validation and isolated caller metadata."""
import unittest
from unittest.mock import patch

from wakfu_server import haven_bag_furniture_catalog as catalog


class FurnitureCatalogTests(unittest.TestCase):
    def setUp(self):
        catalog._catalog.cache_clear()
        self.document = {
            "schema_version": 1,
            "templates": [
                {
                    "template_id": 1532,
                    "type_id": 33,
                    "kind": "PortableCraftTable",
                    "craft_definition_id": 101,
                    "interaction_cells_by_direction": [[[0, 1, 0]]] * 8,
                }
            ],
            "items": [{"item_ref": 9842, "template_id": 1532}],
        }
        self.reader = patch.object(
            catalog.native_catalog, "load", return_value=self.document
        )
        self.reader.start()
        self.addCleanup(self.reader.stop)
        self.addCleanup(catalog._catalog.cache_clear)

    def test_native_item_resolves_craft_metadata_without_mutating_cached_rows(self):
        result = catalog.resolve_item(9842)
        self.assertEqual(
            (result["template_id"], result["craft_definition_id"]), (1532, 101)
        )
        result["interaction_cells_by_direction"][0].clear()
        self.assertEqual(
            catalog.resolve_item(9842)["interaction_cells_by_direction"][0], [[0, 1, 0]]
        )
        templates = catalog.furniture_templates()
        templates[1532]["craft_definition_id"] = -1
        self.assertEqual(
            catalog.furniture_templates()[1532]["craft_definition_id"], 101
        )

    def test_unknown_or_malformed_item_references_do_not_resolve(self):
        for reference in (True, "9842", 0, -1, 999999):
            self.assertIsNone(catalog.resolve_item(reference))

    def test_dangling_template_mapping_is_rejected(self):
        self.document["items"][0]["template_id"] = 9999
        with self.assertRaisesRegex(ValueError, "Unknown furniture template"):
            catalog.resolve_item(9842)

    def test_ambiguous_item_mapping_is_rejected(self):
        self.document["items"].append(dict(self.document["items"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate furniture item"):
            catalog.resolve_item(9842)

    def test_incomplete_direction_metadata_is_rejected(self):
        self.document["templates"][0]["interaction_cells_by_direction"].pop()
        with self.assertRaisesRegex(ValueError, "eight lists"):
            catalog.furniture_templates()


if __name__ == "__main__":
    unittest.main()
