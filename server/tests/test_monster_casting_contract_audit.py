"""Offline audit must distinguish native contradictions from missing authority."""
import copy
import importlib.util
from pathlib import Path
import unittest

_PATH = Path(__file__).resolve().parents[1] / "tools/audit_monster_casting_contracts.py"
_SPEC = importlib.util.spec_from_file_location("monster_casting_contract_audit", _PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


class MonsterCastingContractAuditTests(unittest.TestCase):
    def setUp(self):
        self.table = dict(maximum_level=1, levels=[[0, 0, [11, 12]]], conditional=[])
        self.effects = {
            str(i): dict(native_target_selector=dict(class_="unused", mask=129))
            for i in (11, 12)
        }
        for effect in self.effects.values():
            effect["native_target_selector"]["class"] = "fcE"

    def test_zero_range_other_ally_roots_are_proven_conflict(self):
        self.assertEqual(
            _MODULE.level_contract(self.table, self.effects, 1)[0],
            "blocked_native_ordinary_fcj",
        )

    def test_conditional_native_tables_remain_unknown(self):
        self.table["conditional"] = [dict(criteria="UnknownNativeCriterion()")]
        self.assertEqual(
            _MODULE.level_contract(self.table, self.effects, 1)[0],
            "conditional_unknown",
        )

    def test_missing_selector_is_never_assumed_to_exclude_caster(self):
        del self.effects["11"]["native_target_selector"]
        self.assertEqual(
            _MODULE.level_contract(self.table, self.effects, 1)[0], "unknown"
        )

    def test_null_or_self_accepting_root_breaks_pattern(self):
        for selector in (None, {"class": "fcE", "mask": 1}):
            with self.subTest(selector=selector):
                self.effects["11"]["native_target_selector"] = selector
                self.assertEqual(
                    _MODULE.level_contract(self.table, self.effects, 1)[0],
                    "outside_pattern",
                )

    def test_nonzero_range_does_not_claim_native_conflict(self):
        self.table["levels"][0][1] = 2
        self.assertEqual(
            _MODULE.level_contract(self.table, self.effects, 1)[0], "outside_pattern"
        )

    def test_native_level_clamp_is_reported_without_mutation(self):
        inventory = dict(
            monsters=[
                dict(
                    ref=2617,
                    name="White bow meow",
                    min_level=4,
                    max_level=6,
                    abilities=[dict(spell_id=2794, level_parameter=-1)],
                )
            ]
        )
        before = copy.deepcopy((inventory, self.table, self.effects))
        report = _MODULE.audit(inventory, {"2794": self.table}, self.effects)
        self.assertEqual(report["monsters"][0]["normalized_level_range"], [1, 1])
        self.assertEqual(report["monsters"][0]["requested_level_range"], [4, 6])
        self.assertEqual((inventory, self.table, self.effects), before)
        self.assertFalse(report["runtime_changed"])

    def test_level_zero_requires_separate_native_authority(self):
        self.assertEqual(
            _MODULE.level_contract(self.table, self.effects, 0)[0], "unknown"
        )


if __name__ == "__main__":
    unittest.main()
