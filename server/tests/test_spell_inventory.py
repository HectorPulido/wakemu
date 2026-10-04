"""Catalog completeness and preservation of human tracking, not gameplay tests."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "inventory_builder", ROOT / "server/tools/build_spell_inventory.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class InventoryTests(unittest.TestCase):
    def test_complete_catalog_and_manual_review_survives_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            notes = {
                "schema": 1,
                "spells": {
                    "754": {
                        "status": "Prueba pendiente",
                        "notes": "No repetir probe nativo",
                        "owner": "Revisor",
                        "game_verified": False,
                        "evidence": ["ejemplo"],
                    }
                },
                "families": {},
                "states": {},
                "systems": {},
            }
            review = output / "review.json"
            review.write_text(json.dumps(notes, ensure_ascii=False))
            original = review.read_bytes()
            builder.main(output)
            inventory = json.loads((output / "inventory.json").read_text())
            catalog = json.loads((ROOT / "server/protocol/spells.json").read_text())[
                "spells"
            ]
            self.assertEqual(
                {r["id"] for r in inventory["spells"]}, {r["id"] for r in catalog}
            )
            self.assertEqual(len(inventory["spells"]), len(catalog))
            self.assertEqual(
                len({r["id"] for r in inventory["effects"]}),
                inventory["summary"]["effects"],
            )
            self.assertEqual(
                len({r["id"] for r in inventory["states"]}),
                inventory["summary"]["states"],
            )
            self.assertTrue(
                all(
                    not r["name"].startswith("Nombre pendiente")
                    for r in inventory["spells"]
                )
            )
            row = next(r for r in inventory["spells"] if r["id"] == 754)
            self.assertEqual(row["notes"], "No repetir probe nativo")
            self.assertEqual(row["owner"], "Revisor")
            self.assertEqual(row["evidence"], ["ejemplo"])
            self.assertFalse(row["game_verified"])
            self.assertEqual(review.read_bytes(), original)
            self.assertEqual(inventory["summary"]["individual_game_verified"], 0)
            definitions = {r["id"] for r in inventory["effects"]}
            for spell in inventory["spells"]:
                self.assertTrue(set(spell["root_effects"]) <= set(spell["effect_refs"]))
                self.assertTrue(set(spell["effect_refs"]) <= definitions)
            digest = (output / "inventory.json").read_bytes()
            builder.main(output)
            self.assertEqual(review.read_bytes(), original)
            self.assertEqual((output / "inventory.json").read_bytes(), digest)


if __name__ == "__main__":
    unittest.main()
