"""Preserve the isolated opening suite's retained-Nox verification wrapper."""
import importlib, unittest


def qualify():
    helper = importlib.import_module("_qualification_rushu_dd230_native_opening")
    return unittest.TestSuite([helper.qualify()])
