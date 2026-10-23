"""Run the authorized no-commit preview with both scope chains guarded."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest


class DiagnoseReadonlyPreview(unittest.TestCase):
    def runTest(self):
        m = sys.modules["test_nox_full_party_victory_v4"]
        r = m.retained_components[0]
        rushu = sys.modules[
            "test_rushu_dd230_eleven_slot_opening"
        ].RUSHU_ACTUAL_CHECKPOINT
        before = m.verify_retained_component(r)
        rushu_before = rushu["authorized_service_transition_verifier"]()
        case = r["case"]
        ids = tuple(map(id, (case.runtime, case.fight, r["fixture"].store, case.rng)))
        p = Path(
            ".runtime/parallel-readiness-20261021/diagnose_nox_environment_constructor_preview.py"
        )
        spec = importlib.util.spec_from_file_location(
            "_private_nox_fay_exact_preview", p
        )
        helper = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = helper
        spec.loader.exec_module(helper)
        facts = helper.diagnose(r)
        self.assertEqual(
            ids,
            tuple(map(id, (case.runtime, case.fight, r["fixture"].store, case.rng))),
        )
        facts.update(
            ids_unchanged=True,
            verification_before=before,
            verification_after=m.verify_retained_component(r),
            rushu_verification_before=rushu_before,
            rushu_verification_after=rushu["authorized_service_transition_verifier"](),
        )
        Path(
            ".runtime/parallel-readiness-20261021/nox-fay-constructor-exact-preview-failure-with-both-attestations.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([DiagnoseReadonlyPreview()])
