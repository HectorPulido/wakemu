"""Validate the published inventory's evidence boundaries, not game semantics."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ClassConditionGapInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(
            (
                ROOT
                / "docs/reports/combat-inventory/class-condition-gap-inventory.json"
            ).read_text()
        )

    def test_native_structures_are_not_certified_as_complete_predicates(self):
        rows = self.inventory["native_structural_classes"]
        self.assertEqual(len(rows), 130)
        self.assertEqual(len({r["native_class"] for r in rows}), 130)
        self.assertTrue(all(not r["functional_complete"] for r in rows))

    def test_all_eighteen_classes_have_explicit_reverse_indices(self):
        self.assertEqual(len(self.inventory["classes"]), 18)
        self.assertEqual(len({r["breed"] for r in self.inventory["classes"]}), 18)
        for condition in self.inventory["conditions"]:
            self.assertEqual(
                set(condition["reverse_index"]), {"spell", "state", "area", "effect"}
            )
            if condition["status"] == "absent":
                self.assertFalse(condition["python_routes"])
            if condition["native_class"]:
                self.assertEqual(
                    condition["native_mapping_authority"],
                    "original eQb/eQd isolated parse",
                )

    def test_keywords_are_not_counted_as_textual_predicates(self):
        names = {r["name"] for r in self.inventory["conditions"]}
        self.assertFalse(
            names & {"if", "then", "else", "not", "and", "or", "True", "False"}
        )
