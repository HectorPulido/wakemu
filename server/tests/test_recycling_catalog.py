import json
import math
import unittest
from pathlib import Path
from wakfu_server import native_catalog


CATALOG = (
    Path(__file__).resolve().parents[1] / "protocol" / "item-recycling-metadata.json"
)


class RecyclingCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(native_catalog.read_text(CATALOG))
        cls.items = cls.document["items"]

    def test_full_native_catalog_and_product_references(self):
        self.assertEqual(20230, self.document["record_count"])
        self.assertEqual(0, self.document["error_count"])
        self.assertEqual(20230, len(self.items))
        references = [row["reference"] for row in self.items.values()]
        self.assertEqual(len(references), len(set(references)))
        self.assertEqual(
            10932, sum(row["recycling_kind"] == "SHARD" for row in self.items.values())
        )
        self.assertEqual(
            2765, sum(row["recycling_kind"] == "POWDER" for row in self.items.values())
        )
        self.assertEqual(
            6533,
            sum(
                row["recycling_kind"] == "NOT_RECYCLABLE" for row in self.items.values()
            ),
        )

        for row in self.items.values():
            kind = row["recycling_kind"]
            product = row["recycling_product_reference"]
            expected = {"SHARD": 27083, "POWDER": 27093, "NOT_RECYCLABLE": 0}[kind]
            self.assertEqual(expected, product, row["reference"])

    def test_every_record_preserves_yield_slot_level_and_criteria_fields(self):
        required = {
            "reference",
            "recycling_kind",
            "recycling_product_reference",
            "not_recyclable_feature",
            "yield_low",
            "yield_high",
            "variable_yield",
            "template_gjv",
            "item_level",
            "equipment_slots",
            "equipment_occupied_slots",
            "raw_criteria",
            "compiled_criteria",
        }
        for key, row in self.items.items():
            with self.subTest(reference=key):
                self.assertEqual(required, set(row))
                self.assertEqual(int(key), row["reference"])
                self.assertIs(type(row["not_recyclable_feature"]), bool)
                self.assertIs(type(row["variable_yield"]), bool)
                self.assertIs(type(row["template_gjv"]), bool)
                self.assertTrue(math.isfinite(row["yield_low"]))
                self.assertTrue(math.isfinite(row["yield_high"]))
                self.assertIs(type(row["item_level"]), int)
                self.assertTrue(
                    all(type(slot) is int for slot in row["equipment_slots"])
                )
                self.assertTrue(
                    all(type(slot) is int for slot in row["equipment_occupied_slots"])
                )
                self.assertTrue(
                    all(type(value) is str for value in row["raw_criteria"].values())
                )
                self.assertEqual(
                    sorted(row["compiled_criteria"]), row["compiled_criteria"]
                )

    def test_native_delete_conditions_and_not_recyclable_flag_anomaly_are_retained(
        self,
    ):
        delete = {
            int(key): row["raw_criteria"]["DELETE"]
            for key, row in self.items.items()
            if "DELETE" in row["raw_criteria"]
        }
        self.assertEqual(24, len(delete))
        self.assertEqual(21, sum(value == "False" for value in delete.values()))
        self.assertEqual("IsAchievementComplete(1409)", delete[17496])
        self.assertEqual("GetInstanceId()!=702", delete[17605])
        self.assertEqual(
            "GetInstanceId() <> 1076 and GetInstanceId() <> 1073", delete[20385]
        )
        self.assertTrue(
            all(
                "DELETE" in self.items[str(reference)]["compiled_criteria"]
                for reference in delete
            )
        )

        flagged = [row for row in self.items.values() if row["not_recyclable_feature"]]
        self.assertEqual(44, len(flagged))
        self.assertTrue(all(row["recycling_kind"] == "SHARD" for row in flagged))
        self.assertTrue(
            all(row["recycling_product_reference"] == 27083 for row in flagged)
        )

    def test_native_yield_factor_golden_values(self):
        shard = self.items["12"]
        self.assertEqual(
            ("SHARD", 27083, True),
            (
                shard["recycling_kind"],
                shard["recycling_product_reference"],
                shard["variable_yield"],
            ),
        )
        # fpB.n uses high when nonnegative, otherwise low; UP.bu reports floor/ceil.
        factor = shard["yield_high"] if shard["yield_high"] >= 0 else shard["yield_low"]
        self.assertAlmostEqual(0.07874507, factor)
        self.assertEqual((0, 1), self.preview(1 * factor))
        self.assertEqual((0, 1), self.preview(1 * factor * 1.2))

        powder = self.items["27083"]
        self.assertEqual(
            ("POWDER", 27093),
            (powder["recycling_kind"], powder["recycling_product_reference"]),
        )
        self.assertFalse(powder["variable_yield"])
        powder_factor = (
            powder["yield_high"] if powder["yield_high"] >= 0 else powder["yield_low"]
        )
        self.assertEqual(1.0, powder_factor)
        self.assertEqual((1, 1), self.preview(powder_factor))

    @staticmethod
    def preview(value):
        return math.floor(value), math.ceil(value)


if __name__ == "__main__":
    unittest.main()
