"""Pay one lawful footprint-targeted hit from the retained Rushu endpoint."""
import importlib, unittest


def qualify():
    helper = importlib.import_module(
        "_qualification_rushu264_retained_first_legal_damage"
    )
    guard = importlib.import_module("_qualification_rushu264_drop_with_nox_preserved")
    return unittest.TestSuite([guard.PreserveNoxSuite(helper.qualify())])
