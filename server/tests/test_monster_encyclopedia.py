import json, unittest
from pathlib import Path
from wakfu_server import native_catalog

ROOT = Path(__file__).resolve().parents[2]


class EncyclopediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(
            native_catalog.read_bytes(
                ROOT / "server/protocol/monster-encyclopedia.json"
            )
        )

    def test_every_existing_monster_reference_is_exported(self):
        original = json.loads(
            native_catalog.read_text(ROOT / "server/protocol/monsters.json")
        )
        self.assertEqual(
            {m["ref"] for m in original["monsters"]},
            {m["ref"] for m in self.data["monsters"]},
        )
        self.assertEqual(self.data["count"], len(self.data["monsters"]))

    def test_drop_translation_preserves_native_values_and_criteria(self):
        for monster in self.data["monsters"]:
            native = monster["raw_native"]["csr"]
            drops = monster["combat_drops"]
            self.assertEqual(len(native), len(drops))
            for raw, drop in zip(native, drops):
                for target, source in [
                    ("reference_id", "aAi"),
                    ("probability", "cmY"),
                    ("roll_count", "csD"),
                    ("quantity_min", "cqy"),
                    ("quantity_max", "cqz"),
                    ("is_loot_table", "cqA"),
                    ("complex_criteria", "csH"),
                ]:
                    self.assertEqual(drop[target], raw[source])
                flattened = [
                    v for c in drop["conditions"] for v in (c["id"], c["value"])
                ]
                self.assertEqual(flattened, raw["csG"])
                self.assertTrue(
                    all(c["native_enum"] is not None for c in drop["conditions"])
                )

    def test_external_tables_keep_original_expression_and_nested_data(self):
        tables = self.data["external_loot_tables"]
        self.assertGreater(len(tables), 2000)
        self.assertTrue(any(entry["czk"] for table in tables for entry in table["gBN"]))
        for table in tables:
            for entry in table["gBN"]:
                self.assertIn("gBO", entry)

    def test_unknown_experience_is_not_silently_zero(self):
        self.assertIsNone(self.data["base_combat_xp"])
        self.assertIn("unknown", self.data["availability"]["base_combat_xp"])
