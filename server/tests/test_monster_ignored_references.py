"""Explicit ignored references stay inventoried and outside activation."""
import json
from pathlib import Path
import unittest

from monster_activation_exceptions import (
    ENCOUNTER_EXCEPTIONS,
    IGNORED_NO_BOOK_REFERENCES,
    IGNORED_INCOMPLETE_REFERENCES,
    exception_reason,
    exclusion_status,
)
from prepare_monster_spell_activation import select_candidates


class MonsterIgnoredReferenceTests(unittest.TestCase):
    def test_ignored_snapshot_matches_the_reviewed_low_level_inventory(self):
        root = Path(__file__).resolve().parents[2]
        inventory = json.loads(
            (root / "docs/reports/monster-combat/ACTIVATION_STATUS.json").read_text()
        )
        expected = {
            row["ref"]
            for row in inventory["monsters"]
            if row["max_level"] < 10 and row["status"] == "no_owned_spells"
        }
        self.assertEqual(IGNORED_NO_BOOK_REFERENCES, expected)
        self.assertEqual(len(expected), 382)
        self.assertEqual(IGNORED_INCOMPLETE_REFERENCES, {3118})
        self.assertFalse(expected.intersection(ENCOUNTER_EXCEPTIONS))

    def test_explicit_ignored_ids_stay_excluded_even_if_marked_covered(self):
        ignored = IGNORED_NO_BOOK_REFERENCES | IGNORED_INCOMPLETE_REFERENCES
        rows = [
            dict(
                ref=reference,
                status="covered",
                spell_ids=[1],
                data_gaps=[],
                missing_families=[],
                min_level=1,
                max_level=1,
            )
            for reference in sorted(ignored | {6})
        ]
        for maximum in (9, 100, 30000):
            self.assertEqual(
                [row["ref"] for row in select_candidates({"monsters": rows}, maximum)],
                [6],
            )

    def test_reasons_distinguish_user_ignored_and_encounter_exceptions(self):
        self.assertEqual(exclusion_status(1134), "excluded_no_owned_spells")
        self.assertEqual(exclusion_status(3118), "excluded_incomplete_data")
        self.assertEqual(exclusion_status(3174), "excluded_native_encounter")
        self.assertIsNone(exclusion_status(6))
        self.assertIsNone(exception_reason(6))


if __name__ == "__main__":
    unittest.main()
