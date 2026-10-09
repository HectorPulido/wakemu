"""Pure casting inventory tests: structural evidence, no native startup."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "casting_contract_inventory",
    Path(__file__).resolve().parents[1] / "tools/audit_casting_contracts.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CastingContractInventoryTests(unittest.TestCase):
    def definition(self, maximum=4):
        return dict(
            levels=[[0, maximum, []]],
            line_of_sight=True,
            linear=False,
            free_cell=False,
            range_modifiable=False,
            conditional=[],
        )

    def test_zero_range_is_preserved_and_false_flag_is_complete(self):
        report = module.audit_contracts({"1": self.definition(0)}, {}, [])
        self.assertEqual(report["groups"]["baseline_zero_maximum"]["spell_ids"], [1])
        self.assertNotIn("baseline_missing_range_modifiable", report["groups"])

    def test_conditional_changes_group_every_related_class(self):
        first = self.definition()
        first["conditional"] = [
            dict(
                criteria="state",
                ranges=[[1, 6]],
                line_of_sight=False,
                linear=False,
                free_cell=False,
                range_modifiable=True,
            )
        ]
        inventory = [
            dict(id=1, breed=9, kind="active"),
            dict(id=2, breed=1, kind="passive"),
        ]
        report = module.audit_contracts({"1": first, "2": first}, {}, inventory)
        group = report["groups"]["conditional_range_varies"]
        self.assertEqual(group["class_ids"], [1, 9])
        self.assertEqual(group["active_class_spell_ids"], [1])
        self.assertIn("conditional_line_of_sight_varies", report["groups"])

    def test_missing_flags_in_conditional_and_baseline_are_distinct(self):
        definition = self.definition()
        del definition["range_modifiable"]
        definition["conditional"] = [dict(criteria="state", ranges=[[0, 4]])]
        report = module.audit_contracts({"1": definition}, {}, [])
        self.assertIn("baseline_missing_range_modifiable", report["groups"])
        self.assertIn("conditional_missing_range_modifiable", report["groups"])

    def test_baseline_mismatch_and_missing_definition_are_counted(self):
        report = module.audit_contracts(
            {"1": self.definition()},
            {"1": self.definition(8), "2": self.definition()},
            [],
        )
        self.assertIn("class_baseline_levels_or_roots_mismatch", report["groups"])
        self.assertEqual(
            report["groups"]["class_missing_native_casting_definition"]["spell_ids"],
            [2],
        )

    def test_extended_native_levels_do_not_invent_baseline_mismatch(self):
        native = self.definition()
        native["levels"].append([0, 5, []])
        report = module.audit_contracts({"1": native}, {"1": self.definition()}, [])
        self.assertIn("class_baseline_level_count_differs", report["groups"])
        self.assertNotIn("class_baseline_levels_or_roots_mismatch", report["groups"])


if __name__ == "__main__":
    unittest.main()
