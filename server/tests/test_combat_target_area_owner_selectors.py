import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_targets import (
    _native_target_valid,
    native_selector_policy,
    UnsupportedTargetSelector,
)


class AreaOwnerSelectorTests(unittest.TestCase):
    def setUp(self):
        self.source = SimpleNamespace(id=1)
        self.target = SimpleNamespace(id=2)
        self.context = {
            1: dict(is_Qq=True, q_owner_id=2),
            2: dict(bEe=True, is_eGj=True, is_Qq=False, is_eHH=False, dTE=False),
        }

    def valid(self, mask):
        return _native_target_valid(mask, self.source, self.target, self.context)

    def test_four_native_summon_owner_truth_combinations_and_mixed_masks(self):
        for summoned in (False, True):
            for owned in (False, True):
                self.context[2]["dTE"] = summoned
                self.context[1]["q_owner_id"] = 2 if owned else 3
                for mask in (
                    1 << 44,
                    1 << 46,
                    (1 << 44) | (1 << 46),
                    32 | (1 << 44),
                    (1 << 47) | (1 << 46),
                ):
                    expected = (
                        (not mask & (1 << 44) or not summoned)
                        and (not mask & (1 << 46) or owned)
                        and (not mask & 32 or summoned)
                    )
                    with self.subTest(summoned=summoned, owned=owned, mask=mask):
                        self.assertEqual(self.valid(mask), expected)
                        self.assertFalse(
                            native_selector_policy(
                                {
                                    "native_target_selector": {
                                        "class": "fcE",
                                        "mask": mask,
                                    }
                                }
                            )["in_area"]
                        )

    def test_actual_nonfighter_and_nonarea_types_reject(self):
        self.context[2]["is_eGj"] = False
        self.assertFalse(self.valid(1 << 44))
        self.context[1]["is_Qq"] = False
        self.assertFalse(self.valid(1 << 46))

    def test_null_owner_rejects_without_inventing_owner_or_chain(self):
        self.context[1]["q_owner_id"] = None
        self.assertFalse(self.valid(1 << 46))
        del self.context[1]["q_owner_id"]
        with self.assertRaises(UnsupportedTargetSelector):
            self.valid(1 << 46)
        self.context[1]["q_owner_id"] = True
        with self.assertRaises(UnsupportedTargetSelector):
            self.valid(1 << 46)

    def test_native_short_circuit_checks_types_before_unneeded_facts(self):
        del self.context[2]["dTE"]
        self.context[2]["is_eGj"] = False
        self.assertFalse(self.valid(1 << 44))
        self.context[1] = {"is_Qq": False}
        self.assertFalse(self.valid(1 << 46))

    def test_area_owner_target_needs_explicit_area_retention_flag(self):
        self.context[2].update(is_eGj=False, is_Qq=True, bcR=False)
        self.assertFalse(self.valid(1 << 46))
        self.assertTrue(self.valid((1 << 46) | (1 << 51)))


if __name__ == "__main__":
    unittest.main()
