"""Use the current explicit Nox chain around a same-Store Rushu continuation."""
import importlib
import sys
import unittest


class CurrentChainSerialSuite(unittest.TestSuite):
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
    entry = importlib.import_module("_qualification_rushu_a11_continue_native_jump_los")
    return unittest.TestSuite(
        [CurrentChainSerialSuite([entry.ContinueA11NativeJumpLos()])]
    )
