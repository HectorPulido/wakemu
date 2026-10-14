"""Equal spell identities never transfer actual coverage between actors."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from aggregate_monster_spell_context_proofs import aggregate


class ContextAggregationTests(unittest.TestCase):
    def test_same_spell_other_actor_is_not_actual_coverage(self):
        index = {
            "actual_case_cache": [
                {
                    "reference": 1,
                    "actor_level": 2,
                    "spell_id": 3,
                    "spell_level": 2,
                    "status": "validated",
                    "proof_key": "a",
                }
            ],
            "spell_index": {
                "3": {
                    "resolved_native_level_contexts": [
                        {
                            "ref": ref,
                            "native_level_parameter": -1,
                            "native_actor_ranges": [[2, 2]],
                        }
                        for ref in (1, 2)
                    ]
                }
            },
            "blocks": [],
            "receipt_contexts": {},
        }
        rows = aggregate(index)["rows"]
        self.assertEqual(rows[0]["validated_exact_native_contexts"], 1)
        self.assertEqual(rows[1]["validated_exact_native_contexts"], 0)
        self.assertFalse(rows[0]["monster_qualified"])

    def test_override_levels_are_exact_without_clamping(self):
        index = {
            "actual_case_cache": [],
            "spell_index": {
                "3": {
                    "resolved_native_level_contexts": [
                        {
                            "ref": 1,
                            "native_level_parameter": 0,
                            "native_actor_ranges": [[2, 3]],
                        }
                    ]
                }
            },
            "blocks": [],
            "receipt_contexts": {},
        }
        self.assertEqual(
            aggregate(index)["rows"][0]["expected_exact_native_contexts"], 2
        )


if __name__ == "__main__":
    unittest.main()
