"""Resume only the uncommitted native END using the explicit linked code chain."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest


class ContinueNativeCalendar(unittest.TestCase):
    def runTest(self):
        nox = sys.modules["test_nox_full_party_victory_v4"]
        nr = nox.retained_components[0]
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        rushu_verify = cp["authorized_service_transition_verifier"]
        before = rushu_verify()
        path = Path(
            ".runtime/staging/nox-cube24-fixed12-joint/continue_nox_v4_upgraded_calendar.py"
        )
        spec = importlib.util.spec_from_file_location(
            "_private_nox_v4_upgraded_continuation", path
        )
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        try:
            facts = m.continue_actual(
                verify_upgraded=nr["authorized_scoped_policy_transition_verifier"],
                cancel_path=".runtime/parallel-readiness-20261021/nox-v4-upgraded-stop-requested",
            )
            self.assertTrue(
                facts.get("native_victory"),
                json.dumps(
                    {k: facts.get(k) for k in ("status", "score", "terminal", "final")},
                    default=str,
                ),
            )
        finally:
            after = rushu_verify()
            Path(
                ".runtime/parallel-readiness-20261021/rushu-a11-verification-around-nox-v4-upgraded-continuation.json"
            ).write_text(
                json.dumps(dict(before=before, after=after), indent=2, default=str)
                + "\n"
            )


def qualify():
    return unittest.TestSuite([ContinueNativeCalendar()])
