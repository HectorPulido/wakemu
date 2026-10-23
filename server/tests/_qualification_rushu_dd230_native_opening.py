"""One offensive230 admission and first-round earned action, retaining its Store."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


def _held_nox_verifiers():
    result = []
    for name, module in list(sys.modules.items()):
        if name.startswith("test_nox") and module is not None:
            records = getattr(module, "retained_components", ())
            verify = getattr(module, "verify_retained_component", None)
            if records and callable(verify):
                for record in records:
                    verify(record)
                    result.append((verify, record))
    return result


class SerialOpeningSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        verifiers = _held_nox_verifiers()
        try:
            return super().run(result, debug)
        finally:
            for verify, record in verifiers:
                verify(record)


def qualify():
    # The actor-point fix is already loaded before the current Nox encounter.
    # Only import a new isolated test module; never refresh production here.
    name = "test_rushu_dd230_native_opening"
    previous = sys.modules.get(name)
    assert previous is None or previous.RUSHU_ACTUAL_CHECKPOINT is None
    binder = importlib.import_module("_qualification_rushu264_full_cycle5_retained")
    path = Path(
        ".runtime/staging/rushu-dd230-native-opening/rushu_dd230_native_opening.py"
    )
    spec = importlib.util.spec_from_file_location(name, path)
    recipe = importlib.util.module_from_spec(spec)
    sys.modules[name] = recipe
    spec.loader.exec_module(recipe)
    recipe.RUSHU_HOLD_ACTUAL_CHECKPOINT = True
    recipe.RUSHU_LOADED_IMPLEMENTATION_BINDER = binder._admission_binder(recipe)
    suite = SerialOpeningSuite()
    suite.addTests(
        unittest.defaultTestLoader.loadTestsFromName(
            "RushuDD230NativeOpeningTests.test_normal_party_heals_and_rotates_native_nearest_recipient",
            recipe,
        )
    )
    return suite
