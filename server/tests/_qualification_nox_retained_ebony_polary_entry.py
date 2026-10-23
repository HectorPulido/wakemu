"""Run a single bounded continuation on the original admitted paid Nox case."""
import importlib.util, sys, unittest


class RetainedEbonyPolary(unittest.TestCase):
    def runTest(self):
        key = "_private_nox_retained_ebony_polary"
        spec = importlib.util.spec_from_file_location(
            key,
            ".runtime/staging/nox-cube24-fixed12-joint/continue_retained_ebony_polary.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
        result = module.run()
        self.assertEqual(
            result["status"], "passed_earned_ebony_paid_hit_and_polarynox_birth_only"
        )


def qualify():
    return unittest.TestSuite([RetainedEbonyPolary()])
