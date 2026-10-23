"""Continue the authentic PC4 endpoint with the separately frozen tactical driver."""
import importlib.util, sys, unittest


def qualify():
    key = "_private_continue_full_native_nox_score_v2"
    spec = importlib.util.spec_from_file_location(
        key,
        ".runtime/staging/nox-cube24-fixed12-joint/continue_full_native_nox_score_v2.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return unittest.TestSuite([unittest.FunctionTestCase(module.continue_actual)])
