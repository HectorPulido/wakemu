"""Profile one pending legitimate paid action while protecting settled Nox."""
import importlib
import sys
import unittest


class ProfileOnePaidAction(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        record = sys.modules["test_nox_full_party_victory_v5"].retained_components[0]
        verify_nox = record["authorized_scoped_policy_transition_verifier"]
        verify_nox(record)
        try:
            module = importlib.import_module(
                "_qualification_rushu_single_action_profile"
            )
            result = module.profile_next_cast(
                cp,
                identity=2,
                spell=4777,
                cell=(-48, 6, -4),
                expected=dict(
                    table=12,
                    turn=72,
                    current=2,
                    ap=9,
                    mp=5,
                    wp=3,
                    position=[-47, 6, -4],
                ),
                output=".runtime/rushu-phase-review-20261021/rushu-a11-one-actual-paid-call-profile.json",
            )
            self.assertEqual(result["status"], "paid_call_returned")
        finally:
            verify_nox(record)


def qualify():
    return unittest.TestSuite([ProfileOnePaidAction()])
