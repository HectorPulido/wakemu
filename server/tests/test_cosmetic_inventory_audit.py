"""Offline inventory audit distinguishes native categories, actions and equipment."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "cosmetic_inventory_builder",
    Path(__file__).resolve().parents[1] / "tools/build_cosmetic_inventory.py",
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class CosmeticInventoryAuditTests(unittest.TestCase):
    def build(self, action_class="bIt"):
        return builder.build(
            {
                "categories": [
                    {"id": 6, "name": "PLAYER_AURA"},
                    {"id": 7, "name": "PLAYER_TITLE"},
                ],
                "items": [
                    {"reference": 29764, "class": "bIt", "action_id": 1},
                    {"reference": 11431, "class": "bIs", "action_id": 2},
                ],
            },
            {"items": [{"reference": 29764, "category": 6, "action_id": 1}]},
            {
                "items": [
                    {
                        "reference": 29764,
                        "use_action_class": action_class,
                        "use_action_id": 1,
                    },
                    {"reference": 20720},
                    {"reference": 11431},
                ]
            },
            {
                "items": [
                    {
                        "reference": 20720,
                        "item_level": 200,
                        "effects": [{"generic": 304, "values": [4570, 1, -1]}],
                    }
                ]
            },
            {"items": [{"reference": 20720, "slots": [17]}]},
            {
                29764: "Aura del dofus prismático",
                20720: "Dofus prismático",
                11431: "Título Edad de los Dofus",
                999: "Dofus absent",
            },
        )

    def test_equipment_state_and_learnable_aura_remain_distinct(self):
        result = self.build()
        index = {row["reference"]: row for row in result["dofus_named_items"]}
        self.assertEqual(index[20720]["state_refs"], [4570])
        self.assertIsNone(index[20720]["cosmetic"])
        self.assertEqual(index[29764]["cosmetic"]["category"], 6)
        self.assertEqual(index[29764]["state_refs"], [])
        self.assertIsNone(index[999]["command"])

    def test_empty_native_category_is_not_claimed_as_missing_from_game(self):
        result = self.build()
        self.assertEqual(result["categories"][1]["learning"], "no_bIt_source_in_export")
        title = next(
            row
            for row in result["other_cosmetic_related_actions"]
            if row["class"] == "bIs"
        )
        self.assertEqual(title["count"], 1)

    def test_mismatched_published_action_has_no_grant_probe(self):
        result = self.build("bIx")
        self.assertEqual(result["summary"]["published_matching_bIt_items"], 0)
        self.assertIsNone(result["categories"][0]["items"][0]["command"])
