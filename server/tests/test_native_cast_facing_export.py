"""Static Lua contracts: preserve unknowns rather than execute Lua."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "cast_facing_export",
    Path(__file__).parents[1] / "tools/export_native_cast_facing.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CastFacingExportTest(unittest.TestCase):
    def test_common_defaults(self):
        record = module.extract('params={"useCast",true}\nexecuteScript(1040,params)')
        self.assertTrue(record["turnCasterTowardTargetCell"])
        self.assertFalse(record["useDiags"])
        self.assertFalse(record["casterAnimOnTarget"])

    def test_literal_false_and_diagonal(self):
        record = module.extract(
            'params={"turnCasterTowardTargetCell",false,"useDiags",true,"casterAnimOnTarget",true}\nexecuteScript(1040,params)'
        )
        self.assertFalse(record["turnCasterTowardTargetCell"])
        self.assertTrue(record["useDiags"])
        self.assertTrue(record["casterAnimOnTarget"])

    def test_dynamic_and_other_templates_unknown(self):
        for source in (
            'params={"useDiags",computed}\nexecuteScript(1040,params)',
            "params={}\nexecuteScript(1060,params)",
            "params={} params={} executeScript(1040,params)",
        ):
            self.assertEqual(module.extract(source)["status"], "pending")
