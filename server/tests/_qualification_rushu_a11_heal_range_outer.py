"""Keep cross-scope verification around the corrected retained healing route."""
import importlib
import unittest


def qualify():
    return unittest.TestSuite(
        [
            importlib.import_module(
                "_qualification_rushu_a11_continue_native_heal_range"
            ).qualify()
        ]
    )
