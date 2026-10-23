"""Keep the authorized serial suite intact under the central runner loader."""
import importlib
import unittest


def qualify():
    entry = importlib.import_module("_qualification_rushu_dd230_eleven_slot_opening")
    return unittest.TestSuite([entry.qualify()])
