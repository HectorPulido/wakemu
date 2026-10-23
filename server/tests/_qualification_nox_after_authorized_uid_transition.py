"""Resume the original uncommitted auxiliary after the explicit UID-code transition."""
import importlib.util, sys, unittest


class ContinueAdoptedNox(unittest.TestCase):
    def runTest(self):
        recipe = sys.modules["test_nox_full_party_early_score"]
        record = recipe.retained_components[0]
        verifier = record["authorized_uid_transition_verifier"]
        key = "_private_continue_full_native_nox_score_v3"
        spec = importlib.util.spec_from_file_location(
            key,
            ".runtime/staging/nox-cube24-fixed12-joint/continue_full_native_nox_score_v3.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
        module.continue_actual(verify_adopted=verifier)


def qualify():
    return unittest.TestSuite([ContinueAdoptedNox()])
