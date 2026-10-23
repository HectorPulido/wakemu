"""Assert the original paid journal without replaying its rotation."""
import importlib.util
import sys
import unittest


class RetainedPaidRotation(unittest.TestCase):
    def runTest(self):
        key = "_private_nox_retained_paid_rotation"
        spec = importlib.util.spec_from_file_location(
            key,
            ".runtime/staging/nox-cube24-fixed12-joint/qualify_retained_paid_rotation.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
        result = module.qualify()
        self.assertEqual(result["damage"], 25453)
        self.assertTrue(
            result["loaded_code_verification"]["loaded_implementation_unchanged"]
        )


def qualify():
    return unittest.TestSuite([RetainedPaidRotation()])
