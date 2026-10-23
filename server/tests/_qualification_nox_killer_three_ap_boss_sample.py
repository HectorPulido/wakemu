"""Spend only the killer's legitimate remaining AP on the original retained boss."""
import importlib, importlib.util, sys, unittest


def qualify():
    key = "_private_nox_native_boss_killer_three_ap"
    spec = importlib.util.spec_from_file_location(
        key,
        ".runtime/staging/nox-cube24-fixed12-joint/continue_native_boss_paid_window.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    guard = importlib.import_module("_qualification_nox_prelude_with_rushu_preserved")
    return unittest.TestSuite(
        [guard.PreserveRushuSuite([unittest.FunctionTestCase(module.continue_actual)])]
    )
