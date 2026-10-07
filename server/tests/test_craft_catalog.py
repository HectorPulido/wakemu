import copy
import json
import tempfile
import unittest
from pathlib import Path

from wakfu_server import craft_catalog


class CraftCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(
            (craft_catalog.DATA_ROOT / "craft-recipes.json").read_text()
        )

    def load_document(self, document):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recipes.json"
            path.write_text(json.dumps(document))
            return craft_catalog.load(path)

    def test_full_catalog_counts_and_native_recipe_2047_are_preserved(self):
        recipes = craft_catalog.load()
        self.assertEqual(5449, len(recipes))
        self.assertEqual(5449, len(set(recipes)))
        self.assertEqual(
            34049, sum(len(row["ingredients"]) for row in recipes.values())
        )
        self.assertEqual(5449, sum(len(row["products"]) for row in recipes.values()))
        self.assertEqual(
            {
                "recipe_id": 2047,
                "profession_id": 40,
                "minimum_level": 0,
                "raw_duration": 1000,
                "ingredients": [
                    {"item_id": 2279, "quantity": 1, "extra_raw": 1},
                    {"item_id": 2340, "quantity": 5, "extra_raw": 0},
                ],
                "products": [{"item_id": 8047, "quantity": 4}],
            },
            {
                key: recipes[2047][key]
                for key in (
                    "recipe_id",
                    "profession_id",
                    "minimum_level",
                    "raw_duration",
                    "ingredients",
                    "products",
                )
            },
        )
        self.assertEqual([152, 87, 168, 72], recipes[2047]["raw_cvf"])
        self.assertEqual(300, recipes[2047]["raw_cve"])

    def test_catalog_rejects_missing_rows_and_nonzero_export_errors(self):
        missing = copy.deepcopy(self.document)
        missing["recipes"].pop()
        with self.assertRaisesRegex(
            ValueError, "Incomplete crafting catalog extraction"
        ):
            self.load_document(missing)

        errors = copy.deepcopy(self.document)
        errors["summary"]["record_errors"] = 1
        with self.assertRaisesRegex(
            ValueError, "Incomplete crafting catalog extraction"
        ):
            self.load_document(errors)

    def test_catalog_rejects_duplicate_recipe_ids_even_with_matching_counts(self):
        document = copy.deepcopy(self.document)
        first = copy.deepcopy(document["recipes"][0])
        duplicate = copy.deepcopy(first)
        document["recipes"] = [first, duplicate]
        document["summary"].update(
            recipe_records_seen=2,
            recipe_records_exported=2,
            ingredient_records_exported=2 * len(first["ingredients"]),
            product_records_exported=2 * len(first["products"]),
        )
        with self.assertRaisesRegex(
            ValueError, "Duplicate or invalid native recipe identity"
        ):
            self.load_document(document)

    def test_catalog_rejects_missing_or_invalid_recipe_items(self):
        no_ingredients = copy.deepcopy(self.document)
        recipe = no_ingredients["recipes"][0]
        ingredient_count = len(recipe["ingredients"])
        recipe["ingredients"] = []
        no_ingredients["summary"]["ingredient_records_exported"] -= ingredient_count
        with self.assertRaisesRegex(ValueError, "Missing native recipe items"):
            self.load_document(no_ingredients)

        invalid_item = copy.deepcopy(self.document)
        invalid_item["recipes"][0]["ingredients"][0]["quantity"] = True
        with self.assertRaisesRegex(ValueError, "Invalid native recipe item"):
            self.load_document(invalid_item)

    def test_catalog_rejects_missing_ingredient_qualifier_and_invalid_counts(self):
        missing_qualifier = copy.deepcopy(self.document)
        del missing_qualifier["recipes"][0]["ingredients"][0]["extra_raw"]
        with self.assertRaisesRegex(ValueError, "Missing native ingredient qualifier"):
            self.load_document(missing_qualifier)

        invalid_summary = copy.deepcopy(self.document)
        invalid_summary["summary"]["ingredient_records_exported"] = True
        with self.assertRaisesRegex(ValueError, "Invalid crafting catalog counts"):
            self.load_document(invalid_summary)

    def test_station_definitions_and_instances_keep_native_field_meaning(self):
        catalog = craft_catalog.load_catalog()
        self.assertEqual(79, len(catalog.definitions))
        self.assertEqual(330, len(catalog.table_instances))
        self.assertEqual(330, catalog.validation["table_instances_resolved"])

        # The object's text parameter is definition 81, whose profession is 73.
        definition = catalog.definitions[81]
        self.assertEqual(73, definition["profession_id"])
        self.assertEqual(77, definition["station_family_key"])
        self.assertEqual([], definition["allowed_recipe_ids"])
        self.assertIsNone(catalog.resolve_table(999999, 1))

        astrub_tables = [
            row for row in catalog.table_instances if row["map_id"] == 1134
        ]
        self.assertEqual(26, len(astrub_tables))
        self.assertTrue(all(row["status"] == "resolved" for row in astrub_tables))
        resolved = catalog.resolve_table(1134, 31505)
        self.assertEqual(81, resolved["definition_id"])
        self.assertEqual(73, resolved["profession_id"])

    def test_native_permission_uses_allowlist_and_fails_closed_for_unknowns(self):
        catalog = craft_catalog.load_catalog()
        # Native table definition 94 lists recipe 10153 despite the profession
        # metadata mismatch; the native UI's GE/i membership is the permission
        # check, while that mismatch remains visible in the audit data.
        self.assertEqual(81, catalog.definitions[94]["profession_id"])
        self.assertEqual(76, catalog.recipes[10153]["profession_id"])
        self.assertTrue(catalog.authorize_recipe(94, 10153, profession_id=81))
        self.assertFalse(catalog.authorize_recipe(94, 10153, profession_id=76))
        self.assertFalse(catalog.authorize_recipe(94, 999999))
        self.assertFalse(catalog.authorize_recipe(999999, 10153))
        self.assertFalse(catalog.authorize_recipe(True, 10153))
        self.assertFalse(catalog.authorize_recipe(94, True))

        # These IDs are retained as native allowlist data, but cannot authorize
        # crafting while their recipe definitions are missing from the export.
        unknown = next(
            recipe_id
            for row in catalog.definitions.values()
            for recipe_id in row["allowed_recipe_ids"]
            if recipe_id not in catalog.recipes
        )
        definition_id = next(
            identity
            for identity, row in catalog.definitions.items()
            if unknown in row["allowed_recipe_ids"]
        )
        self.assertFalse(catalog.authorize_recipe(definition_id, unknown))

    def test_documented_native_anomalies_are_preserved_without_rejecting_catalog(self):
        catalog = craft_catalog.load_catalog()
        self.assertEqual(
            [81, 138, 139, 191], catalog.validation["empty_allowlist_definition_ids"]
        )
        self.assertEqual(2019, catalog.validation["unknown_allowed_recipe_count"])
        self.assertEqual(2, catalog.validation["profession_mismatch_count"])
        mismatch = catalog.validation["profession_mismatch_examples"]
        self.assertEqual(
            {(94, 10153, 81, 76), (154, 10153, 81, 76)},
            {
                (
                    row["definition_id"],
                    row["recipe_id"],
                    row["table_profession_id"],
                    row["recipe_profession_id"],
                )
                for row in mismatch
            },
        )

    def test_station_loader_rejects_duplicate_definitions_and_bad_instances(self):
        duplicate_definition = copy.deepcopy(self.document)
        duplicate_definition["craft_table_definition_rows"].append(
            copy.deepcopy(duplicate_definition["craft_table_definition_rows"][0])
        )
        with self.assertRaisesRegex(ValueError, "Invalid native crafting definition"):
            self.load_document(duplicate_definition)

        bad_reference = copy.deepcopy(self.document)
        instance = next(
            row
            for row in bad_reference["craft_table_instances"]
            if row["status"] == "resolved"
        )
        instance["profession_id"] += 1
        with self.assertRaisesRegex(
            ValueError, "Inconsistent native CraftTable definition reference"
        ):
            self.load_document(bad_reference)


if __name__ == "__main__":
    unittest.main()
