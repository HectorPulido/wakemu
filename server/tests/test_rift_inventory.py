"""Offline rift identity joins reject missing, ambiguous and mismatched data."""
import copy
import tempfile
import unittest
from pathlib import Path
import zipfile
from tools.build_rift_inventory import build


class RiftInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.locale = Path(self.temp.name) / "locale.jar"
        with zipfile.ZipFile(self.locale, "w") as archive:
            archive.writestr(
                "texts_es.properties",
                "content.7.4=Tofu\ninfinite.waves.player.limit=4\n",
            )
        self.wave = {
            "id": 3,
            "raw_cpb": 1314,
            "raw_cpc": 4160,
            "raw_rI": 21,
            "species_refs": [4],
        }
        self.waves = {"binary_table_id": 147, "records": [self.wave]}
        self.inventory = {
            "records": [
                {
                    "native": {
                        "id": 168,
                        "type": "INFINITE_WAVE",
                        "raw_cnl": 3,
                        "raw_aHA": [1314],
                    },
                    "name_es": "Tainela",
                    "configurations": [],
                    "native_objects": [],
                    "native_exits": [],
                }
            ]
        }

    def run_build(self):
        return build(self.waves, self.inventory, [], self.locale)

    def test_exact_join_preserves_pool_and_level(self):
        result = self.run_build()
        self.assertEqual(result["summary"]["classic"], 1)
        self.assertEqual(
            result["rifts"][0]["species"], [{"reference": 4, "name_es": "Tofu"}]
        )
        self.assertEqual(result["rifts"][0]["level"], 21)

    def test_missing_wave_rejected(self):
        self.waves["records"] = []
        with self.assertRaisesRegex(ValueError, "Missing or ambiguous"):
            self.run_build()

    def test_ambiguous_wave_rejected(self):
        self.waves["records"].append(copy.deepcopy(self.wave))
        with self.assertRaisesRegex(ValueError, "Missing or ambiguous"):
            self.run_build()

    def test_map_mismatch_rejected(self):
        self.wave["raw_cpb"] = 9
        with self.assertRaisesRegex(ValueError, "map mismatch"):
            self.run_build()

    def test_non_public_wave_retained_without_claiming_rift(self):
        self.waves["records"].append(dict(self.wave, id=99))
        self.assertEqual(self.run_build()["unlinked_wave_definitions"][0]["id"], 99)
