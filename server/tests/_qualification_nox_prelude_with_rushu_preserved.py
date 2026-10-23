"""Run the authorized new opening serially while preserving Rushu's original services."""
import importlib.util, json, sys, unittest
from pathlib import Path


class PreserveRushuSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        recipe = sys.modules["test_rushu_native_party_phase_one"]
        before = recipe.verify_actual_checkpoint()
        try:
            return super().run(result, debug)
        finally:
            try:
                after = recipe.verify_actual_checkpoint()
                Path(
                    ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/rushu-original-loaded-code-before-after-new-nox-opening.json"
                ).write_text(
                    json.dumps(
                        dict(before=before, after=after, no_rushu_actions=True),
                        indent=2,
                        default=str,
                    )
                )
            except Exception:
                result.addError(unittest.FunctionTestCase(lambda: None), sys.exc_info())


def qualify():
    recipe = sys.modules["test_rushu_native_party_phase_one"]
    recipe.verify_actual_checkpoint()
    key = "_private_nox_prelude_five_modes_and_polary_qualifier"
    spec = importlib.util.spec_from_file_location(
        key,
        ".runtime/staging/nox-cube24-fixed12-joint/qualify_nox_prelude_five_modes_and_polary.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return unittest.TestSuite([PreserveRushuSuite(module.qualify())])
