"""Diagnostic codes never substitute for native failure stage or criterion."""
import json
import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from group_monster_effect_failures import (
    diagnostic_signature,
    stable_read,
    group_failures,
)


class FailureGroupTests(unittest.TestCase):
    def test_same_code_distinct_criterion_is_distinct_group(self):
        def diagnostic(criterion):
            return {
                "details": {
                    "native_casting_result": "twV",
                    "native_casting_diagnostic": {
                        "criterion": criterion,
                        "trace": [{"stage": "criterion_cell", "value": False}],
                    },
                }
            }

        self.assertNotEqual(
            diagnostic_signature(diagnostic("HasState(1)")),
            diagnostic_signature(diagnostic("HasState(2)")),
        )

    def test_resumed_case_deduplicates_and_preserves_pointer_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            item = {
                "context": {
                    "reference": 1,
                    "actor_level": 2,
                    "spell_id": 3,
                    "spell_level": 2,
                },
                "raw_case": {"status": "validated"},
                "reused": False,
            }
            document = {
                "cases": [item],
                "source_sha256_before": {"a": "b"},
                "candidate_manifest_sha256": "c",
            }
            first = Path(directory) / "first.json"
            first.write_text(json.dumps(document))
            item["reused"] = True
            second = Path(directory) / "second.json"
            second.write_text(json.dumps(document))
            result = group_failures({"spell_index": {}}, [first, second])
            self.assertEqual(result["cases_observed"], 1)
            self.assertEqual(result["duplicate_receipt_entries"], 1)
            self.assertEqual(len(result["proof_aliases"][0]["aliases"]), 2)

    def test_passive_and_zero_source_witnesses_are_not_pending_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            cases = [
                {
                    "context": {
                        "reference": 1,
                        "actor_level": 2,
                        "spell_id": spell,
                        "spell_level": 2,
                    },
                    "raw_case": {"status": status},
                    "reused": False,
                }
                for spell, status in [
                    (3, "passive_initialization_only"),
                    (4, "native_zero_amount_unavailable"),
                ]
            ]
            path.write_text(json.dumps({"cases": cases}))
            result = group_failures({"spell_index": {}}, [path])
            self.assertEqual(result["pending_cases"], 0)
            self.assertEqual(result["source_witness_case_count"], 2)
            self.assertEqual(result["validated_cases"], 0)

    def test_moving_snapshot_fails_closed(self):
        class Moving:
            count = 0

            def read_bytes(self):
                self.count += 1
                return ('{"version":%s}' % self.count).encode()

        with self.assertRaises(ValueError):
            stable_read(Moving(), attempts=2)


if __name__ == "__main__":
    unittest.main()
