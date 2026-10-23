"""Finish the same paid Nox encounter using only native turn boundaries."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest


class FinishEarnedNativeOutcome(unittest.TestCase):
    def runTest(self):
        nox = sys.modules["test_nox_full_party_victory_v5"]
        nr = nox.retained_components[0]
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        rv = cp["authorized_service_transition_verifier"]
        before = rv()
        p = Path(
            ".runtime/staging/nox-cube24-fixed12-joint/continue_nox_v5_earned_score_native_outcome.py"
        )
        spec = importlib.util.spec_from_file_location(
            "_private_nox_v5_earned_score_native_outcome", p
        )
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        try:
            facts = m.continue_actual(
                verify_retained=nox.verify_retained_component, cancel_path=None
            )
            self.assertTrue(
                facts.get("native_victory"),
                str(facts.get("terminal", facts.get("final"))),
            )
        finally:
            after = rv()
            Path(
                ".runtime/parallel-readiness-20261021/rushu-a11-verification-around-nox-v5-earned-native-outcome.json"
            ).write_text(
                json.dumps(dict(before=before, after=after), indent=2, default=str)
                + "\n"
            )


def qualify():
    return unittest.TestSuite([FinishEarnedNativeOutcome()])
