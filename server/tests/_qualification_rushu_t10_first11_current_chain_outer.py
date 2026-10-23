"""Guard the inactive Nox checkpoint during one finite paid Rushu window."""
import importlib
import sys
import unittest


class GuardNoxSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        m = sys.modules["test_nox_full_party_victory_v5"]
        r = m.retained_components[0]
        verify = r["authorized_scoped_policy_transition_verifier"]
        verify(r)
        try:
            return super().run(result, debug)
        finally:
            verify(r)


def qualify():
    m = importlib.import_module("_qualification_rushu_a11_ten_to_first_start_eleven")
    return unittest.TestSuite([GuardNoxSuite([m.ContinueA11TenToFirstStartEleven()])])
