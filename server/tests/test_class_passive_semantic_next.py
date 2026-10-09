"""Source-selected semantic actions remain legal and individually identifiable."""
import json
from pathlib import Path
import sys
import unittest
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_class_passive_semantic_next import PLAN, REPORT, planned_semantic_cases
from wakfu_server.spells import encode_deck, validate_deck


@unittest.skipUnless(
    REPORT.exists(),
    "Frozen offline339 evidence is required for source-case regression tests",
)
class PassiveSemanticNextTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(PLAN.read_text())
        self.report = json.loads(REPORT.read_text())

    def test42legal_cases_preserve_one_declared_owned_or_actual_granted_action(self):
        rows, queues, requested = planned_semantic_cases(self.plan, self.report)
        self.assertEqual(len(rows), 42)
        self.assertEqual(len({row["breed"] for row in rows}), 18)
        self.assertEqual(sum(row["purpose"] == "source_novelty" for row in rows), 36)
        self.assertEqual(
            sum(
                row["fixture_context"] == "source_owned_captured_roster" for row in rows
            ),
            1,
        )
        for row in rows:
            parsed = validate_deck(
                encode_deck(row["active_deck"], [row["passive"]]),
                row["breed"],
                row["level"],
            )
            self.assertEqual(
                requested[
                    row["breed"], row["level"], row["passive"], tuple(parsed["active"])
                ],
                row["action"],
            )

    def test_unknown_unowned_action_cannot_be_smuggled_into_source_case(self):
        altered = deepcopy(self.plan)
        altered["next_bulk"]["proposed_cases"][0]["action"] = 2147483647
        with self.assertRaisesRegex(ValueError, "lacks direct ownership"):
            planned_semantic_cases(altered, self.report)
