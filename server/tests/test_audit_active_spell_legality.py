"""The active audit separates speculative targets from proven live rejects."""
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_active_spells as audit


class ActiveSpellLegalityTests(unittest.TestCase):
    @staticmethod
    def casting_record(*, minimum=1, maximum=1, **overrides):
        record = dict(
            levels=[[minimum, maximum, []]],
            free_cell=False,
            line_of_sight=True,
            linear=False,
            allow_self=False,
            path_option=False,
            diagonal=False,
            linear_path=False,
            range_modifiable=False,
        )
        record.update(overrides)
        return record

    def test_target_candidates_use_native_range_and_occupancy_flags(self):
        baseline = audit.native_casting_baseline(
            self.casting_record(minimum=1, maximum=1, free_cell=True), 1
        )
        with patch.object(audit, "static_visible", return_value=True):
            variants = audit.target_candidates(
                dict(
                    levels=[[0, 9, []]],
                    free_cell=False,
                    line_of_sight=False,
                    linear=False,
                ),
                1,
                {"cells": {(0, 0, 0), (1, 0, 0), (2, 0, 0)}},
                (0, 0, 0),
                native=baseline,
            )
        self.assertEqual(variants, [("empty_cell", (1, 0, 0))])

    def test_target_candidates_use_native_linearity_and_los_flags(self):
        baseline = audit.native_casting_baseline(
            self.casting_record(
                minimum=2,
                maximum=2,
                line_of_sight=False,
                linear=False,
            ),
            1,
        )
        variants = audit.target_candidates(
            dict(
                levels=[[1, 1, []]],
                free_cell=False,
                line_of_sight=True,
                linear=True,
            ),
            1,
            {"cells": {(0, 0, 0), (1, 1, 0), (2, 0, 0)}},
            (0, 0, 0),
            native=baseline,
        )
        self.assertEqual(
            variants,
            [("enemy", (1, 1, 0)), ("empty_cell", (1, 1, 0))],
        )

    def test_target_candidate_generator_requires_complete_native_baseline(self):
        with self.assertRaisesRegex(ValueError, "installed native casting baseline"):
            audit.target_candidates(
                dict(levels=[[0, 99, []]], free_cell=False),
                1,
                {"cells": {(0, 0, 0), (1, 0, 0)}},
                (0, 0, 0),
            )
        incomplete = self.casting_record()
        incomplete.pop("free_cell")
        with self.assertRaisesRegex(ValueError, "baseline flags"):
            audit.native_casting_baseline(incomplete, 1)

    def test_conditional_only_self_permission_is_speculative(self):
        self.assertEqual(
            audit.self_candidate_kind(
                {
                    "allowed": False,
                    "conditional": [
                        {"allowed": True, "criteria": "HasState(55, 'caster')"}
                    ],
                }
            ),
            "speculative_conditional_self_candidate",
        )

    def test_baseline_permission_and_never_allowed_policy_are_distinct(self):
        self.assertEqual(
            audit.self_candidate_kind({"allowed": True, "conditional": []}),
            "baseline_self_candidate",
        )
        self.assertIsNone(
            audit.self_candidate_kind(
                {"allowed": False, "conditional": [{"allowed": False}]}
            )
        )

    def test_only_speculative_range_failure_proven_by_selected_table_is_expected(self):
        candidate = "speculative_conditional_self_candidate"
        reason = "Spell target is outside native range"
        self.assertTrue(
            audit.expected_speculative_range_rejection(
                candidate, reason, 0, 1, 3, False
            )
        )
        self.assertFalse(
            audit.expected_speculative_range_rejection(
                candidate, reason, 0, 0, 3, False
            )
        )
        self.assertFalse(
            audit.expected_speculative_range_rejection(candidate, reason, 0, 1, 3, True)
        )
        self.assertFalse(
            audit.expected_speculative_range_rejection(
                candidate, reason, 1, 1, 3, False
            )
        )
        self.assertFalse(
            audit.expected_speculative_range_rejection(
                "baseline_self_candidate", reason, 0, 1, 3, False
            )
        )
        self.assertFalse(
            audit.expected_speculative_range_rejection(
                candidate, "Spell requires a straight line", 0, 1, 3, False
            )
        )

    def test_native_range_rejection_requires_the_same_selected_table_proof(self):
        candidate = "speculative_conditional_self_candidate"
        reason = "Native spell casting eligibility rejected: twI"
        self.assertTrue(
            audit.expected_speculative_range_rejection(
                candidate, reason, 0, 1, 3, False
            )
        )
        self.assertFalse(
            audit.expected_speculative_range_rejection(
                candidate, reason, 0, 0, 3, False
            )
        )
        self.assertFalse(
            audit.expected_speculative_range_rejection(candidate, reason, 0, 1, 3, True)
        )
        for gate in ("twV", "twE", "twX"):
            self.assertFalse(
                audit.expected_speculative_range_rejection(
                    candidate,
                    "Native spell casting eligibility rejected: " + gate,
                    0,
                    1,
                    3,
                    False,
                )
            )

    def test_diagnostic_serialization_preserves_consumed_identity_without_queries(self):
        class NativeTarget:
            def __init__(self):
                self.uid = 123
                self.cell = (2, 3, 4)

            @property
            def position(self):
                raise AssertionError("Diagnostic must not query native providers")

        diagnostic = audit.casting_diagnostic_json(
            {
                "target": NativeTarget(),
                "consumed": frozenset({9, 2}),
            }
        )
        self.assertEqual(
            diagnostic["target"],
            {
                "native_type": "NativeTarget",
                "identity": {"uid": 123, "cell": [2, 3, 4]},
            },
        )
        self.assertEqual(diagnostic["consumed"], [2, 9])
        self.assertEqual(json.loads(json.dumps(diagnostic)), diagnostic)


if __name__ == "__main__":
    unittest.main()
