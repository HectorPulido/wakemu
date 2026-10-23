"""Continue only the rejected Jump destination while preserving held Nox code."""
import importlib, unittest


def qualify():
    helper = importlib.import_module("_qualification_rushu_dd230_continue_legal_jump")
    guard = importlib.import_module("_qualification_rushu_dd230_native_opening")
    return unittest.TestSuite([guard.SerialOpeningSuite(helper.qualify())])
