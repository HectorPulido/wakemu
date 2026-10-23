"""Observe the authentic remaining calendar without replaying the first pulse."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest


class ObserveNativeTerminal(unittest.TestCase):
    def runTest(self):
        nox = sys.modules["test_nox_full_party_victory_v4"]
        nr = nox.retained_components[0]
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        rv = cp["authorized_service_transition_verifier"]
        before = rv()
        p = Path(
            ".runtime/staging/nox-cube24-fixed12-joint/continue_nox_v4_post_auspice_terminal.py"
        )
        spec = importlib.util.spec_from_file_location(
            "_private_nox_v4_post_auspice_terminal", p
        )
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        try:
            facts = m.continue_actual(
                verify_upgraded=nr["authorized_scoped_policy_transition_verifier"],
                cancel_path=None,
            )
            self.assertIn(
                "terminal",
                facts,
                str({k: facts.get(k) for k in ("status", "score", "final")}),
            )
        finally:
            after = rv()
            Path(
                ".runtime/parallel-readiness-20261021/rushu-a11-verification-around-nox-post-auspice-terminal.json"
            ).write_text(
                json.dumps(dict(before=before, after=after), indent=2, default=str)
                + "\n"
            )


def qualify():
    return unittest.TestSuite([ObserveNativeTerminal()])
