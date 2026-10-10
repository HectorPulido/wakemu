import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "execution_count_import",
    Path(__file__).resolve().parents[1] / "tools" / "import_native_execution_counts.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativeExecutionCountImportTests(unittest.TestCase):
    def fixture(self):
        metadata = {
            "states": {"1": {}},
            "effects": {
                "9": {
                    "effect_class": 999,
                    "event_execution_count": 0,
                    "subscription": True,
                }
            },
        }
        exported = {
            "schema": "native-execution-counts-v1",
            "complete": True,
            "count": 1,
            "source": "eVn.cyc",
            "effects": {
                "9": {
                    "effect_class": 999,
                    "event_execution_count": 0,
                    "event_execution_count_per_level": 1.0,
                }
            },
        }
        return metadata, exported

    def test_additive_merge_preserves_other_authority(self):
        metadata, exported = self.fixture()
        result = module.merge_counts(metadata, exported)
        self.assertEqual(result["effects"]["9"]["event_execution_count_per_level"], 1.0)
        self.assertTrue(result["effects"]["9"]["subscription"])
        self.assertEqual(result["states"], metadata["states"])
        self.assertNotIn("event_execution_count_per_level", metadata["effects"]["9"])

    def test_incomplete_export_is_rejected(self):
        metadata, exported = self.fixture()
        exported["count"] = 2
        with self.assertRaises(ValueError):
            module.merge_counts(metadata, exported)

    def test_identity_and_base_mismatch_rejected(self):
        for field, value in (("effect_class", 330), ("event_execution_count", 3)):
            metadata, exported = self.fixture()
            exported["effects"]["9"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                module.merge_counts(metadata, exported)
