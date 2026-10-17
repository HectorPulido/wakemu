"""Unfinished registrations cannot silently inflate a conservative estimate."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_monster_family_coverage import (
    exclude_unqualified_families,
    supported_families,
)


class FamilyCoverageExclusionTests(unittest.TestCase):
    def test_supported_families_are_extracted_from_current_runtime_sources(self):
        registry = {"effects": {}}
        setters = {"effects": {}}
        families = supported_families(registry, setters)
        self.assertIn(48, families)  # Explicit native effect handler
        self.assertIn(304, families)  # Dynamic state-handler table
        self.assertIn(402, families)  # Explicit cell-null operation
        self.assertIn(649, families)  # Explicit spell-grant operation
        self.assertNotIn(999999, families)

    def test_exclusion_only_removes_support_without_mutating_source(self):
        supported = {830, 994, 1003}
        self.assertEqual(exclude_unqualified_families(supported, [994]), {830, 1003})
        self.assertEqual(supported, {830, 994, 1003})

    def test_default_retains_original_estimate(self):
        self.assertEqual(exclude_unqualified_families({830}, []), {830})

    def test_unknown_duplicate_and_boolean_exclusions_reject(self):
        for excluded in ([99], [830, 830], [True], [0]):
            with self.subTest(excluded=excluded), self.assertRaises(ValueError):
                exclude_unqualified_families({830}, excluded)
