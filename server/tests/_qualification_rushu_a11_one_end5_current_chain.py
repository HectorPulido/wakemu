"""Protect the retained Nox scope around one authorized native Rushu boundary."""
import importlib
import sys
import unittest


class GuardNoxSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        nox = sys.modules["test_nox_full_party_victory_v4"]
        r = nox.retained_components[0]
        verify = r["authorized_scoped_policy_transition_verifier"]
        verify(r)
        try:
            return super().run(result, debug)
        finally:
            verify(r)


def qualify():
    m = importlib.import_module("_qualification_rushu_a11_observe_end_five_after_ko")
    return unittest.TestSuite([GuardNoxSuite([m.ObserveA11EndFiveAfterKo()])])
