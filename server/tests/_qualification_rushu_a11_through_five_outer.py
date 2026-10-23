"""Preserve serial Nox verification around the retained Rushu continuation."""
import importlib
import unittest


def qualify():
    entry = importlib.import_module("_qualification_rushu_a11_continue_through_five")
    return unittest.TestSuite([entry.qualify()])
