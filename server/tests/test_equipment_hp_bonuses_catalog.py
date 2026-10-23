import os
import unittest

from wakfu_server import native_catalog
from wakfu_server.items.equipment_hp_bonuses import descriptor
from wakfu_server.paths import DATA_ROOT


class EquipmentHpBonusesCatalogTests(unittest.TestCase):
    def test_actual_family21_rows_are_classified_by_native_shape(self):
        if not os.environ.get("WAKFU_DATABASE_URL"):
            self.skipTest("requires the focused published-catalog runner")
        document = native_catalog.load(DATA_ROOT / "item-equipment-effects.json")
        items = {item["reference"]: item for item in document["items"]}
        native = native_catalog.load(
            DATA_ROOT / "native-copied-equipment-definitions.json"
        )
        actual = []
        for item in document["items"]:
            for effect in item["effects"]:
                if effect.get("generic") == 21 and effect.get("runner") == "eWO":
                    actual.append((item, effect))
        self.assertEqual(7, len(actual))
        supported = 0
        probabilistic = 0
        for item, effect in actual:
            reference = item["reference"]
            with self.subTest(reference=reference):
                self.assertEqual(-1, effect["stat_id"])
                definition = native["definitions"][str(reference)]
                roots = [
                    root
                    for root in definition["ordered_effects"]
                    if root["reference"] == effect["id"]
                ]
                self.assertEqual(1, len(roots), definition)
                root = roots[0]
                self.assertEqual(21, root["effect_class"])
                self.assertEqual("", root["criterion_raw"])
                self.assertEqual([], root["children"])
                self.assertEqual([], root["child_definitions"])
                self.assertEqual(effect["params"], root["parameters"])
                self.assertTrue(
                    all(type(value) is float for value in root["parameters"])
                )
                self.assertEqual(
                    effect["values"], root["native_values_at_fresh_item_level"]
                )
                metadata = root["metadata"]
                self.assertEqual(
                    {"class": "fcE", "mask": 0}, metadata["native_target_selector"]
                )
                self.assertEqual(0, metadata["native_execution_mode"])
                self.assertIn("native_effect_flags", metadata, metadata)
                self.assertEqual([], metadata["native_effect_flags"])
                operation = descriptor(effect)
                self.assertIsNotNone(operation)
                self.assertEqual(1, operation["stat"])
                self.assertEqual(effect["values"][0], operation["amount"])
                if operation.get("chance", 100) != 100:
                    self.assertEqual(1, operation["chance"])
                    probabilistic += 1
                supported += 1
        self.assertEqual(7, supported)
        self.assertEqual(1, probabilistic)


if __name__ == "__main__":
    unittest.main()
