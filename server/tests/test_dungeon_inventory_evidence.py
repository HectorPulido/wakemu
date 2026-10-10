"""Check the generated evidence matrix does not conflate native and local data."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class DungeonInventoryEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(
            (ROOT / "docs/reports/dungeons/inventory.json").read_text()
        )
        cls.records = cls.inventory["records"]

    def test_union_preserves_every_native_and_guide_identity(self):
        summary = self.inventory["summary"]
        self.assertEqual(len(self.records), summary["union_records"])
        self.assertEqual(len({r["key"] for r in self.records}), len(self.records))
        self.assertEqual(
            sum(r["native"] is not None for r in self.records),
            summary["native_definitions"],
        )
        self.assertEqual(
            sum(len(r["guides"]) for r in self.records), summary["guide_records"]
        )

    def test_internal_destinations_and_exits_are_distinct(self):
        for row in self.records:
            maps = (
                set(row["native"]["raw_aHA"])
                if row["native"]
                else {c["route"]["start_map_id"] for c in row["configurations"]}
            )
            for source in row["native_internal_teleports"]:
                self.assertIn(source["source_map"], maps)
                self.assertTrue(source["destinations"])
                self.assertTrue(
                    all(d["map_id"] in maps for d in source["destinations"])
                )
            for source in row["native_exits"]:
                self.assertIn(source["source_map"], maps)
                self.assertTrue(source["destinations"])
                self.assertTrue(
                    all(d["map_id"] not in maps for d in source["destinations"])
                )

    def test_reported_gate_and_teleport_dungeons_have_native_evidence(self):
        by_id = {r["native"]["id"]: r for r in self.records if r["native"]}
        self.assertEqual(by_id[27]["native_object_type_counts"]["Door"], 3)
        self.assertFalse(by_id[27]["native_internal_teleports"])
        self.assertNotIn("Door", by_id[90]["native_object_type_counts"])
        self.assertEqual(len(by_id[90]["native_internal_teleports"]), 4)

    def test_species_pools_do_not_claim_encounter_composition(self):
        for row in self.records:
            if row["native"]:
                self.assertEqual(
                    [m["ref_id"] for m in row["native_species_pool"]],
                    row["native"]["raw_cno"],
                )
            self.assertTrue(row["unknowns"])
            for configuration in row["configurations"]:
                self.assertIs(configuration["official"], False)
                self.assertIs(
                    configuration["topology"]["official_room_order_verified"], False
                )


if __name__ == "__main__":
    unittest.main()
