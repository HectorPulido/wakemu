"""Execute the bounded survivor tactic on the authentic Nox case."""
import importlib, importlib.util, sys, unittest


def qualify():
    key = "_private_nox_native_polary_paid_ko"
    spec = importlib.util.spec_from_file_location(
        key,
        ".runtime/staging/nox-cube24-fixed12-joint/continue_native_polary_paid_ko.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    guard = importlib.import_module("_qualification_nox_prelude_with_rushu_preserved")
    return unittest.TestSuite(
        [guard.PreserveRushuSuite([unittest.FunctionTestCase(module.continue_actual)])]
    )
