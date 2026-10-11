"""Regression coverage for disjoint native monster activation cohorts."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server" / "tools"))

from monster_activation_exceptions import (  # noqa: E402
    ENCOUNTER_EXCEPTIONS,
    IGNORED_INCOMPLETE_REFERENCES,
    IGNORED_NO_BOOK_REFERENCES,
)
from prepare_monster_spell_activation import (  # noqa: E402
    inventory_activation_status,
    select_candidates,
)


class MonsterActivationScopeTests(unittest.TestCase):
    def test_selected_references_are_pending_candidates(self):
        self.assertEqual(
            inventory_activation_status(42, {42}, set()),
            "candidate_pending_execution_validation",
        )

    def test_previously_enabled_references_remain_activated(self):
        self.assertEqual(inventory_activation_status(42, set(), {"42"}), "activated")

    def test_explicit_exclusions_take_precedence_over_selection_and_prior_activation(
        self,
    ):
        excluded = next(iter(ENCOUNTER_EXCEPTIONS))
        self.assertEqual(
            inventory_activation_status(excluded, {excluded}, {str(excluded)}),
            "excluded_native_encounter",
        )

    def test_status_classification_does_not_mutate_cohort_inputs(self):
        selected = {42}
        previously_enabled = {"41"}
        selected_before = selected.copy()
        enabled_before = previously_enabled.copy()

        inventory_activation_status(41, selected, previously_enabled)

        self.assertEqual(selected, selected_before)
        self.assertEqual(previously_enabled, enabled_before)

    def test_level_49_cohort_excludes_reviewed_low_ranges_and_all_user_exceptions(self):
        coverage_path = (
            ROOT / "docs" / "reports" / "monster-combat" / "ALL_LEVELS_COVERAGE.json"
        )
        coverage = json.loads(coverage_path.read_text())
        reviewed_low_range = {
            row["ref"] for row in coverage["monsters"] if row["max_level"] <= 9
        }
        excluded = (
            IGNORED_NO_BOOK_REFERENCES
            | IGNORED_INCOMPLETE_REFERENCES
            | set(ENCOUNTER_EXCEPTIONS)
        )

        candidates = [
            row
            for row in select_candidates(coverage, maximum=49)
            if row["ref"] not in reviewed_low_range
        ]
        candidate_refs = {row["ref"] for row in candidates}

        self.assertEqual(len(candidates), 303)
        self.assertTrue(candidate_refs.isdisjoint(reviewed_low_range))
        self.assertTrue(candidate_refs.isdisjoint(excluded))
        self.assertTrue(
            all(1 <= row["min_level"] <= row["max_level"] <= 49 for row in candidates)
        )


if __name__ == "__main__":
    unittest.main()
