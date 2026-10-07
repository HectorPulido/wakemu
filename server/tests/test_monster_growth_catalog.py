import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "server" / "protocol"
MONSTERS_PATH = PROTOCOL / "monsters.json"
RESOURCES_PATH = PROTOCOL / "plant-resources.json"
CATALOG_PATH = PROTOCOL / "monster-growth-catalog.json"
EXPORTER_PATH = ROOT / "server" / "tools" / "export_monster_growth_catalog.py"


class MonsterGrowthCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.monsters = json.loads(MONSTERS_PATH.read_text())["monsters"]
        cls.resources = json.loads(RESOURCES_PATH.read_text())
        cls.catalog_bytes = CATALOG_PATH.read_bytes()
        cls.catalog = json.loads(cls.catalog_bytes)

    def test_embedded_source_hashes_match_current_inputs(self):
        expected = {
            "monsters": hashlib.sha256(MONSTERS_PATH.read_bytes()).hexdigest(),
            "resources": hashlib.sha256(RESOURCES_PATH.read_bytes()).hexdigest(),
        }
        self.assertEqual(expected, self.catalog["source_sha256"])

    def test_family_and_candidate_coverage_matches_source_records(self):
        source_families = {}
        for resource in self.resources:
            if resource["monster_resource"]:
                for family in resource["monster_family_ids"]:
                    source_families.setdefault(family, set()).add(
                        resource["resource_reference"]
                    )

        catalog_families = {row["family_id"]: row for row in self.catalog["families"]}
        self.assertEqual(set(source_families), set(catalog_families))
        all_candidates = []
        for family, resource_refs in source_families.items():
            row = catalog_families[family]
            self.assertEqual(sorted(resource_refs), row["resource_references"])
            all_candidates.extend(
                candidate["reference"]
                for tier in row["tiers"]
                for candidate in tier["candidates"]
            )
        source_refs = {
            row["ref"] for row in self.monsters if row["family_id"] in source_families
        }
        self.assertEqual(720, len(all_candidates))
        self.assertEqual(720, len(set(all_candidates)))
        self.assertEqual(source_refs, set(all_candidates))

    def test_known_tiers_and_missing_families_are_stable(self):
        families = {row["family_id"]: row for row in self.catalog["families"]}
        self.assertEqual(
            {394, 469, 470},
            {family for family, row in families.items() if row["missing_catalog"]},
        )
        self.assertTrue(families[532]["terminal"])
        self.assertEqual(1, len(families[532]["tiers"]))
        self.assertEqual(
            [2465, 2466, 2467, 2468],
            [item["reference"] for item in families[532]["tiers"][0]["candidates"]],
        )
        for family, expected in {
            68: {4: [2, 39], 8: [1], 10: [41], 14: [3], 18: [4085], 23: [44, 4086]},
            81: {4: [6], 8: [4], 10: [5], 14: [704], 18: [4092], 23: [1259, 4101]},
        }.items():
            actual = {
                tier["min_level"]: [
                    candidate["reference"] for candidate in tier["candidates"]
                ]
                for tier in families[family]["tiers"]
            }
            self.assertEqual(expected, actual)

    def test_native_world_property_classification_matches_source(self):
        source_by_ref = {row["ref"]: row for row in self.monsters}
        classifications = Counter()
        catalog_candidates = {
            candidate["reference"]: candidate
            for family in self.catalog["families"]
            for tier in family["tiers"]
            for candidate in tier["candidates"]
        }
        for reference, candidate in catalog_candidates.items():
            native_properties = source_by_ref[reference]["raw_visual_arrays"]["csc"]
            self.assertEqual(native_properties, candidate["world_properties"])
            if 49 in native_properties:
                expected = "ultimate_boss"
            elif 99 in native_properties:
                expected = "raid_boss"
            elif 43 in native_properties:
                expected = "boss"
            elif 45 in native_properties:
                expected = "arch"
            else:
                expected = "regular"
            self.assertEqual(expected, candidate["boss_classification"], reference)
            classifications[expected] += 1

        self.assertEqual(
            {"regular": 524, "boss": 110, "arch": 86}, dict(classifications)
        )
        for reference in (44, 1259):
            self.assertIn(43, catalog_candidates[reference]["world_properties"])
            self.assertEqual(
                "boss", catalog_candidates[reference]["boss_classification"]
            )
        self.assertIn("BOSS43", self.catalog["boss_classification"])
        self.assertIn("no name heuristics", self.catalog["boss_classification"])

    def test_export_is_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            outputs = [Path(temp_dir) / "first.json", Path(temp_dir) / "second.json"]
            for output in outputs:
                subprocess.run(
                    [
                        sys.executable,
                        str(EXPORTER_PATH),
                        "--monsters",
                        str(MONSTERS_PATH),
                        "--resources",
                        str(RESOURCES_PATH),
                        "--output",
                        str(output),
                    ],
                    check=True,
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
            self.assertEqual(outputs[0].read_bytes(), outputs[1].read_bytes())
            self.assertEqual(self.catalog_bytes, outputs[0].read_bytes())


if __name__ == "__main__":
    unittest.main()
