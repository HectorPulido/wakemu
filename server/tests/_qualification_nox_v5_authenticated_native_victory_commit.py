"""Commit the authenticated native helper cleanup with full cross-scope guards."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest


class CommitActualNativeVictory(unittest.TestCase):
    def runTest(self):
        m = sys.modules["test_nox_full_party_victory_v5"]
        r = m.retained_components[0]
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        rv = cp["authorized_service_transition_verifier"]
        before = rv()
        p = Path(
            ".runtime/staging/nox-cube24-fixed12-joint/commit_nox_v5_authenticated_terminal_cleanup.py"
        )
        spec = importlib.util.spec_from_file_location(
            "_private_commit_nox_v5_authenticated_cleanup", p
        )
        entry = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = entry
        spec.loader.exec_module(entry)
        try:
            facts = entry.commit_actual(
                verify_adopted=r["authorized_scoped_policy_transition_verifier"]
            )
            self.assertTrue(facts.get("native_victory"))
        finally:
            after = rv()
            Path(
                ".runtime/parallel-readiness-20261021/rushu-a11-verification-around-nox-v5-native-victory-commit.json"
            ).write_text(
                json.dumps(dict(before=before, after=after), indent=2, default=str)
                + "\n"
            )


def qualify():
    return unittest.TestSuite([CommitActualNativeVictory()])
