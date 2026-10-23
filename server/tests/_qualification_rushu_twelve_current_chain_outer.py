"""Protect the settled Nox result during the next retained Rushu window."""
import importlib
import sys
import unittest


class GuardNoxSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        record = sys.modules["test_nox_full_party_victory_v5"].retained_components[0]
        verify = record["authorized_scoped_policy_transition_verifier"]
        verify(record)
        try:
            return super().run(result, debug)
        finally:
            verify(record)


def qualify():
    module = importlib.import_module("_qualification_rushu_a11_twelve_before_fourteen")
    return unittest.TestSuite(
        [GuardNoxSuite([module.ContinueA11TwelveBeforeFourteen()])]
    )
