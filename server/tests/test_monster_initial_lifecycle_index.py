"""Lifecycle evidence stays distinct from owned-spell execution."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_initial_lifecycle_index import build_initial_lifecycle_index


class InitialLifecycleTests(unittest.TestCase):
    def test_constructor_family_keeps_null_spell_and_explicit_path(self):
        result = build_initial_lifecycle_index(
            [
                {
                    "ref": 1,
                    "initial_states": [{"state_id": 7}],
                    "abilities": [{"spell_id": 20}],
                }
            ],
            {
                "8": {
                    "family": 803,
                    "children": set(),
                    "references": set(),
                    "criteria": 'HasState(9, "caster")',
                }
            },
            {"7": {"8"}},
            {},
            {},
            set(),
        )
        self.assertIsNone(result["rows"][0]["spell_id"])
        self.assertEqual(result["rows"][0]["path"], [("state", "7"), ("effect", "8")])
        self.assertFalse(result["rows"][0]["execution_proven"])
        self.assertEqual(
            result["dependency_groups"][0]["projected_affected_owned_spell_ids"], [20]
        )

    def test_missing_state_is_explicit_not_empty_success(self):
        result = build_initial_lifecycle_index(
            [{"ref": 1, "initial_states": [{"state_id": 7}]}], {}, {}, {}, {}, set()
        )
        self.assertEqual(result["rows"][0]["missing_source_node"], ["state", "7"])


if __name__ == "__main__":
    unittest.main()
