"""Profile one pending legitimate paid action while protecting settled Nox."""
import importlib
import sys
import unittest


class ReadCurrentJumpGeometry(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        record = sys.modules["test_nox_full_party_victory_v5"].retained_components[0]
        verify_nox = record["authorized_scoped_policy_transition_verifier"]
        verify_nox(record)
        try:
            module = importlib.import_module(
                "_qualification_rushu_fourteen_jump_readonly"
            )
            module.diagnose(
                cp,
                ".runtime/rushu-phase-review-20261021/rushu-fourteen-pc4-native-jump-rays-readonly.json",
            )
        finally:
            verify_nox(record)


def qualify():
    return unittest.TestSuite([ReadCurrentJumpGeometry()])
