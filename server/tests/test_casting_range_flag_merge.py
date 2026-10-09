"""Native range import joins exact criteria without filling absent data."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "casting_range_flag_merge",
    Path(__file__).resolve().parents[1] / "tools/merge_casting_range_flags.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CastingRangeFlagMergeTests(unittest.TestCase):
    def catalogs(self):
        return (
            {"spells": {"1": {"conditional": [{"criteria": "a"}, {"criteria": "b"}]}}},
            {
                "spells": {
                    "1": {
                        "range_modifiable": False,
                        "conditional": [
                            {"criteria": "b", "range_modifiable": True},
                            {"criteria": "a", "range_modifiable": False},
                        ],
                    }
                }
            },
        )

    def test_exact_join_is_independent_of_rule_order_and_preserves_inputs(self):
        casting, flags = self.catalogs()
        result = module.merge_flags(casting, flags)
        row = result["spells"]["1"]
        self.assertFalse(row["range_modifiable"])
        self.assertEqual(
            [r["range_modifiable"] for r in row["conditional"]], [False, True]
        )
        self.assertNotIn("range_modifiable", casting["spells"]["1"])

    def test_missing_references_are_rejected(self):
        casting, flags = self.catalogs()
        flags["spells"]["2"] = flags["spells"]["1"]
        with self.assertRaisesRegex(ValueError, "references differ"):
            module.merge_flags(casting, flags)

    def test_missing_conditional_flag_is_rejected(self):
        casting, flags = self.catalogs()
        del flags["spells"]["1"]["conditional"][0]["range_modifiable"]
        with self.assertRaisesRegex(ValueError, "Missing native conditional"):
            module.merge_flags(casting, flags)

    def test_duplicate_criteria_are_rejected(self):
        casting, flags = self.catalogs()
        flags["spells"]["1"]["conditional"][0]["criteria"] = "a"
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            module.merge_flags(casting, flags)


if __name__ == "__main__":
    unittest.main()
