import unittest
from conditional_committed_observations import reconcile


class ConditionalCommittedObservationTests(unittest.TestCase):
    def test_unique_and_equivalent_known_match_are_separate(self):
        matrix = {"rows": [{"spell": 1, "branch": 0, "criterion_raw": "HasState(2)"}]}
        selection = {
            "reference": 1,
            "evaluation_level": 20,
            "table_index": 19,
            "matched_rules": [{"index": 0, "criteria": "HasState(2)"}],
            "unknown_equivalent_rule_indices": [],
            "selected_values": [1],
            "baseline_values": [0],
            "unique_matching_rule": True,
        }
        row = {
            "reference": 1,
            "commit_status": "committed",
            "source_preserved": True,
            "native_casting_selection": selection,
        }
        result = reconcile([row], matrix)
        self.assertEqual(len(result["unique_selected_committed"]), 1)
        selection["unknown_equivalent_rule_indices"] = [1]
        selection["unique_matching_rule"] = False
        result = reconcile([row], matrix)
        self.assertEqual(len(result["known_matched_committed"]), 1)
        self.assertFalse(
            result["known_matched_committed"][0][
                "removal_or_producer_semantics_verified"
            ]
        )

    def test_uncommitted_and_criterion_mismatch_cannot_certify_branch(self):
        row = {
            "reference": 1,
            "commit_status": "rejected",
            "source_preserved": True,
            "native_casting_selection": {},
        }
        self.assertEqual(len(reconcile([row], {"rows": []})["rejected"]), 1)
