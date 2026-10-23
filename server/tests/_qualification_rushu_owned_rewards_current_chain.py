"""Persist the same native result without replaying any combat action."""
import importlib.util
from pathlib import Path
import sys
import unittest


class PersistRushuRewards(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        nr = sys.modules["test_nox_full_party_victory_v5"].retained_components[0]
        verify_nox = nr["authorized_scoped_policy_transition_verifier"]
        verify_nox(nr)
        try:
            path = Path(
                ".runtime/staging/rushu-owned-terminal-rewards/persist_rushu_actual_owned_rewards.py"
            )
            spec = importlib.util.spec_from_file_location(
                "_rushu_actual_owned_reward_adapter", path
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            result = module.persist_actual(
                verify_current=cp["authorized_service_transition_verifier"]
            )
            self.assertTrue(result["full_victory"])
        finally:
            verify_nox(nr)


def qualify():
    return unittest.TestSuite([PersistRushuRewards()])
