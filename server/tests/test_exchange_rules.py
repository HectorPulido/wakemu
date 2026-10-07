import json
import unittest
from pathlib import Path

from wakfu_server import exchange_rules


class ExchangeRulesCatalogTests(unittest.TestCase):
    def test_full_export_has_no_missing_or_duplicate_reference_records(self):
        catalog = exchange_rules.CATALOG
        items = catalog["items"]
        references = [item["reference"] for item in items.values()]
        self.assertEqual(20230, catalog["raw_records"])
        self.assertEqual(catalog["raw_records"], catalog["loaded_records"])
        self.assertEqual(0, catalog["errors"])
        self.assertEqual(20230, len(items))
        self.assertEqual(len(references), len(set(references)))
        self.assertTrue(all(str(row["reference"]) == key for key, row in items.items()))

    def test_native_false_literals_pickup_binding_and_unbound_golden_cases(self):
        self.assertEqual(
            {"False": 80, "Faux": 2},
            {
                literal: sum(
                    item["raw_criteria"].get("EXCHANGE") == literal
                    for item in exchange_rules.ITEMS.values()
                )
                for literal in ("False", "Faux")
            },
        )
        self.assertFalse(exchange_rules.eligibility(10216))  # Java False literal.
        self.assertFalse(exchange_rules.eligibility(14055))  # French Faux literal.
        self.assertFalse(
            exchange_rules.eligibility(2603)
        )  # BOUND_ON_PICKUP_TO_ACCOUNT.
        self.assertFalse(
            exchange_rules.eligibility(8244)
        )  # BOUND_ON_PICKUP_TO_CHARACTER.
        self.assertFalse(exchange_rules.eligibility(2603, bound=False))
        self.assertFalse(exchange_rules.eligibility(8244, bound=False))
        self.assertTrue(exchange_rules.eligibility(12))
        self.assertFalse(exchange_rules.eligibility(12, bound=True))
        self.assertTrue(exchange_rules.eligibility(12, bound=False))

    def test_mount_catalog_uses_native_binding_and_exchange_criteria_without_mount_override(
        self,
    ):
        mounts = json.loads(
            (Path(__file__).parents[1] / "protocol" / "mount-models.json").read_text(
                encoding="utf-8"
            )
        )["models"]
        self.assertEqual(40, len(mounts))
        known = 0
        unknown = []
        for mount in mounts:
            reference = mount["reference"]
            item = exchange_rules.ITEMS.get(str(reference))
            if item is None:
                unknown.append(reference)
                with self.assertRaisesRegex(ValueError, "Unknown native"):
                    exchange_rules.eligibility(reference)
                continue
            known += 1
            default_bound = item["binding_template"]["default_eKo"]
            self.assertIs(type(default_bound), bool, reference)
            self.assertEqual(
                not default_bound, exchange_rules.eligibility(reference), reference
            )

        self.assertEqual(37, known)
        self.assertEqual([20622, 20624, 20638], sorted(unknown))
        # These installed mount models are natively bound on pickup; the result
        # comes from the item catalog, not a special-case mount rule.
        for reference in (18682, 18704):
            self.assertTrue(
                exchange_rules.ITEMS[str(reference)]["binding_template"]["default_eKo"]
            )
            self.assertFalse(exchange_rules.eligibility(reference))

    def test_unknown_references_and_unrecognized_native_fields_fail_closed(self):
        for reference in (0, -1, True, 1 << 31, "12", None):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                exchange_rules.eligibility(reference)
        for bound in (0, 1, "false", {}):
            with self.subTest(bound=bound), self.assertRaisesRegex(
                ValueError, "binding"
            ):
                exchange_rules.eligibility(12, bound=bound)

        item = exchange_rules.ITEMS["12"]
        original = item["raw_criteria"].get("EXCHANGE")
        item["raw_criteria"]["EXCHANGE"] = "unknown-native-expression"
        try:
            with self.assertRaisesRegex(ValueError, "criterion"):
                exchange_rules.eligibility(12)
        finally:
            if original is None:
                item["raw_criteria"].pop("EXCHANGE", None)
            else:
                item["raw_criteria"]["EXCHANGE"] = original
