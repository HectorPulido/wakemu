"""Continue the single retained full native Nox encounter without readmission."""
import importlib.util, sys, unittest


def qualify():
    key = "_private_continue_full_native_nox_score"
    spec = importlib.util.spec_from_file_location(
        key,
        ".runtime/staging/nox-cube24-fixed12-joint/continue_full_native_nox_score.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return unittest.TestSuite([unittest.FunctionTestCase(module.continue_actual)])
