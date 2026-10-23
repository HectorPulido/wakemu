"""Reload only the corrected recipe harness and continue the already-earned pickup."""
import importlib, unittest


def qualify():
    helper = importlib.reload(
        importlib.import_module("_qualification_rushu264_retained_paid_drop_damage")
    )
    guard = importlib.import_module("_qualification_rushu264_drop_with_nox_preserved")
    return unittest.TestSuite([guard.PreserveNoxSuite(helper.qualify())])
