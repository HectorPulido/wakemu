"""Observe one native boundary while protecting the settled Nox scope."""
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
    module = importlib.import_module(
        "_qualification_rushu_a11_observe_native_start_twelve"
    )
    return unittest.TestSuite([GuardNoxSuite([module.ObserveA11NativeStartTwelve()])])
