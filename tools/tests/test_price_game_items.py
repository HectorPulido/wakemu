"""Offline regression and artifact audits for the shop price proposal."""
import csv
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "price-game-items.py"
POLICY_PATH = ROOT / "docs/reports/item-pricing-20261011/pricing-policy.json"
OUTPUT = ROOT / "docs/reports/item-pricing-20261011"
SOURCE = ROOT / "docs/reports/item-shop-inventory-20261011/curated/all-items.csv"

spec = importlib.util.spec_from_file_location("price_game_items", SCRIPT)
pricing_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pricing_module)
Pricing = pricing_module.Pricing


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def synthetic_engine(items, crafts=None, overrides=None):
    inventory = [{"reference": str(item["reference"])} for item in items]
    native = {"items": items, "types": [{"type_id": 100, "parent_id": -1}]}
    docs = {
        "item-stack-rules.json": {"items": []},
        "item-equipment-effects.json": {"items": []},
        "item-action-rules.json": {"items": []},
        "item-healing-rules.json": {"items": []},
        "item-shard-effects.json": {"items": []},
    }
    snapshot = {"documents": docs}
    return Pricing(
        inventory,
        snapshot,
        native,
        {"items": {}},
        {"by_item": crafts or {}},
        [],
        json.loads(POLICY_PATH.read_text()),
        overrides,
    )


class SyntheticPricingTests(unittest.TestCase):
    def test_rarity_zero_exceeds_common_and_relic_exceeds_epic(self):
        engine = synthetic_engine(
            [
                {"reference": 1, "type_id": 100, "level": 50, "rarity_id": 0},
                {"reference": 2, "type_id": 100, "level": 50, "rarity_id": 1},
                {"reference": 3, "type_id": 100, "level": 50, "rarity_id": 5},
                {"reference": 4, "type_id": 100, "level": 50, "rarity_id": 7},
            ]
        )
        self.assertGreater(engine.baseline(1)[0], engine.baseline(2)[0])
        self.assertGreater(engine.baseline(3)[0], engine.baseline(4)[0])

    def test_recipe_cost_is_per_output_unit_and_cycle_is_not_recursed(self):
        items = [
            {"reference": 20720, "type_id": 100, "level": 1, "rarity_id": 1},
            {"reference": 20, "type_id": 100, "level": 10, "rarity_id": 1},
            {"reference": 30, "type_id": 100, "level": 10, "rarity_id": 1},
        ]
        crafts = {
            "20": {
                "recipes": [
                    {
                        "recipe_id": 200,
                        "usable_for_cost": True,
                        "yield_quantity": 4,
                        "ingredients": [{"reference": 20720, "quantity": 1}],
                        "minimum_level": 0,
                        "ingredient_slot_count": 1,
                        "raw_duration": 0,
                    }
                ]
            },
            "30": {
                "recipes": [
                    {
                        "recipe_id": 300,
                        "usable_for_cost": True,
                        "yield_quantity": 1,
                        "ingredients": [{"reference": 30, "quantity": 1}],
                        "minimum_level": 0,
                        "ingredient_slot_count": 1,
                        "raw_duration": 0,
                    }
                ]
            },
        }
        engine = synthetic_engine(items, crafts)
        crafted = engine.price(20)
        self.assertEqual(crafted["craft_cost"], 2500000)
        self.assertEqual(crafted["route"], "craft")
        cyclic = engine.price(30)
        self.assertIn("cyclic_recipe_skipped", cyclic["flags"])
        self.assertEqual(cyclic["craft_depth"], 0)

    def test_manual_override_propagates_through_recursive_recipe_cost(self):
        items = [
            {"reference": 40, "type_id": 100, "level": 10, "rarity_id": 1},
            {"reference": 20, "type_id": 100, "level": 10, "rarity_id": 1},
        ]
        crafts = {
            "20": {
                "recipes": [
                    {
                        "recipe_id": 200,
                        "usable_for_cost": True,
                        "yield_quantity": 2,
                        "ingredients": [{"reference": 40, "quantity": 1}],
                        "minimum_level": 0,
                        "ingredient_slot_count": 1,
                        "raw_duration": 0,
                    }
                ]
            }
        }
        overrides = {"40": {"price_kamas": 40000}}
        engine = synthetic_engine(items, crafts, overrides)
        crafted = engine.price(20)
        self.assertEqual(engine.price(40)["price"], 40000)
        self.assertEqual(crafted["craft_cost"], 20000)
        self.assertEqual(crafted["craft_inputs"][0]["unit_price"], 40000)

    def test_price_floor_and_ceiling_are_applied(self):
        engine = synthetic_engine(
            [
                {"reference": 1, "type_id": 100, "level": 1, "rarity_id": 1},
                {"reference": 2, "type_id": 100, "level": 99999, "rarity_id": 4},
            ]
        )
        engine.policy["groups"]["equipment"]["base"] = 0.01
        engine.policy["groups"]["equipment"]["cap"] = engine.policy["maximum"]
        self.assertEqual(engine.price(1)["price"], 100)
        engine.policy["groups"]["equipment"]["base"] = 1_000_000_000
        self.assertEqual(engine.price(2)["price"], engine.policy["maximum"])


class GeneratedArtifactAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_rows = read_csv(SOURCE)
        cls.rows = read_csv(OUTPUT / "prices.csv")
        cls.summary = json.loads((OUTPUT / "summary.json").read_text())

    def test_priced_ids_exactly_partition_curated_source(self):
        source_ids = [int(row["reference"]) for row in self.source_rows]
        priced_ids = [int(row["reference"]) for row in self.rows]
        self.assertEqual(len(source_ids), len(set(source_ids)))
        self.assertEqual(len(priced_ids), len(set(priced_ids)))
        self.assertEqual(set(priced_ids), set(source_ids))
        category_rows = []
        for path in OUTPUT.glob("prices-*.csv"):
            category_rows.extend(read_csv(path))
        category_ids = [int(row["reference"]) for row in category_rows]
        self.assertEqual(len(category_ids), len(set(category_ids)))
        self.assertEqual(set(category_ids), set(source_ids))

    def test_all_prices_are_integer_unit_prices_in_policy_bounds(self):
        policy = json.loads(POLICY_PATH.read_text())
        self.assertEqual(len(self.rows), 18816)
        for row in self.rows:
            value = int(row["price_kamas"])
            self.assertEqual(row["quantity"], "1", row["reference"])
            self.assertGreaterEqual(value, policy["minimum"], row["reference"])
            self.assertLessEqual(value, policy["maximum"], row["reference"])

    def test_only_six_curated_true_dofus_receive_ten_million(self):
        policy = json.loads(POLICY_PATH.read_text())
        prices = {int(row["reference"]): row for row in self.rows}
        expected = set(policy["true_dofus_refs"])
        actual = {
            ref
            for ref, row in prices.items()
            if row["economic_group"] == "dofus"
            and int(row["price_kamas"]) == 10_000_000
        }
        self.assertEqual(actual, expected)
        decorative = [
            row
            for row in self.rows
            if "dofus" in row["name_es"].lower()
            and int(row["reference"]) not in expected
        ]
        self.assertTrue(decorative)
        self.assertTrue(all(int(row["price_kamas"]) < 10_000_000 for row in decorative))

    def test_admin_quality_has_six_holds(self):
        admin = [row for row in self.rows if row["rarity_id"] == "10"]
        self.assertEqual(len(admin), 6)
        self.assertTrue(
            all(
                "admin_quality_hold" in row["publication_hold"].split("|")
                for row in admin
            )
        )

    def test_manual_review_index_covers_every_curated_reference_and_holds_match(self):
        index = json.loads((OUTPUT / "manual-review-index.json").read_text())
        rows_by_ref = {row["reference"]: row for row in self.rows}
        self.assertEqual(index["total_references"], len(self.source_rows))
        self.assertEqual(set(index["by_reference"]), {str(ref) for ref in rows_by_ref})
        holds = [row for row in self.rows if row["publication_hold"]]
        self.assertEqual(len(holds), 1769)
        for row in self.rows:
            review = index["by_reference"][row["reference"]]
            self.assertEqual(row["manual_review_by"], review["reviewer"])
            self.assertEqual(
                bool(row["manual_hold_reason"]), bool(review["hold_reasons"])
            )
            self.assertEqual(
                "manual_publication_hold" in row["flags"].split("|"),
                bool(review["hold_reasons"]),
            )

    def test_manual_changes_separate_direct_overrides_from_propagated_recipe_changes(
        self,
    ):
        changed = [
            row
            for row in self.rows
            if row["price_kamas"] != row["automated_price_kamas"]
        ]
        direct = [row for row in changed if row["manual_override_reviewer"]]
        propagated = [row for row in changed if not row["manual_override_reviewer"]]
        self.assertEqual(
            len(json.loads((OUTPUT / "manual-overrides.json").read_text())), 301
        )
        self.assertEqual(len(direct), 293)
        self.assertEqual(len(propagated), 609)
        self.assertEqual(len(changed), 902)
        self.assertTrue(
            all(
                row["manual_override_reason"] and row["manual_override_reviewer"]
                for row in self.rows
                if row["manual_override_reviewer"]
            )
        )

    def test_unmatched_drop_evidence_is_not_reported_as_impossible_acquisition(self):
        rows = [
            row for row in self.rows if row["acquisition"] == "unresolved_source_policy"
        ]
        self.assertTrue(rows)
        self.assertTrue(
            all(
                "no_verified_drop_craft_or_harvest" in row["flags"].split("|")
                for row in rows
            )
        )
        evidence = (OUTPUT / "drop-evidence.md").read_text().lower()
        self.assertIn("not proof that the item has no acquisition route", evidence)

    def test_excluded_inventory_stays_out_of_shop_price_partition(self):
        excluded_path = (
            ROOT
            / "docs/reports/item-shop-inventory-20261011/curated/excluded-items.csv"
        )
        excluded_ids = {int(row["reference"]) for row in read_csv(excluded_path)}
        priced_ids = {int(row["reference"]) for row in self.rows}
        self.assertTrue(excluded_ids)
        self.assertFalse(excluded_ids & priced_ids)

    def test_summary_hashes_match_input_and_generated_csv_files(self):
        for filename, expected_hash in self.summary["source_sha256"].items():
            path = ROOT / filename
            self.assertTrue(path.is_file(), filename)
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(), expected_hash, filename
            )
        for filename, expected_hash in self.summary["artifacts_sha256"].items():
            path = OUTPUT / filename
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(), expected_hash, filename
            )


if __name__ == "__main__":
    unittest.main()
