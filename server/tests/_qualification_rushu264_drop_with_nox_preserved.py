"""Run one paid Rushu continuation while preserving the retained Nox implementation."""
import importlib, json, sys, unittest
from pathlib import Path


class PreserveNoxSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        nox = sys.modules["test_nox_prelude_five_modes_and_polary"]
        record = nox.retained_components[0]
        before = nox.verify_retained_component(record)
        try:
            return super().run(result, debug)
        finally:
            try:
                after = nox.verify_retained_component(record)
                Path(
                    ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox-original-loaded-code-before-after-rushu-drop.json"
                ).write_text(
                    json.dumps(
                        dict(before=before, after=after, no_nox_actions=True),
                        indent=2,
                        default=str,
                    )
                )
            except Exception:
                result.addError(unittest.FunctionTestCase(lambda: None), sys.exc_info())


def qualify():
    helper = importlib.import_module(
        "_qualification_rushu264_retained_paid_drop_damage"
    )
    return unittest.TestSuite([PreserveNoxSuite(helper.qualify())])
