"""Persist the retained native result while protecting the other live scope."""
import importlib.util
from pathlib import Path
import sys
import unittest


class PersistCurrentNoxRewards(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        verify_rushu = cp["authorized_service_transition_verifier"]
        record = sys.modules["test_nox_full_party_victory_v5"].retained_components[0]
        verify_nox = record["authorized_scoped_policy_transition_verifier"]
        verify_rushu()
        try:
            path = Path(
                ".runtime/staging/nox-cube24-fixed12-joint/persist_nox_v5_actual_owned_rewards.py"
            )
            spec = importlib.util.spec_from_file_location(
                "_nox_v5_actual_owned_reward_adapter", path
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            result = module.persist_actual(verify_adopted=verify_nox)
            self.assertTrue(result["full_victory"])
        finally:
            self.assertIs(
                cp,
                sys.modules[
                    "test_rushu_dd230_eleven_slot_opening"
                ].RUSHU_ACTUAL_CHECKPOINT,
            )
            verify_rushu()


def qualify():
    return unittest.TestSuite([PersistCurrentNoxRewards()])
