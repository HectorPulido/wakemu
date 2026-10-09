"""Native universal passive ownership and complete initialization catalogs."""
import json
import struct
import unittest
from wakfu_server import spells
from wakfu_server.paths import DATA_ROOT
from wakfu_server import native_catalog


class CommonPassiveOwnershipTests(unittest.TestCase):
    def test_every_class_receives_common_passives_at_native_thresholds(self):
        common = {
            4957: 10,
            4958: 15,
            4956: 25,
            5237: 35,
            5146: 55,
            5145: 65,
            5144: 75,
            5621: 80,
        }
        breeds = {s["breed"] for s in spells.SPELLS.values() if s["breed"] > 0}
        for breed in breeds:
            for reference, threshold in common.items():
                with self.subTest(breed=breed, reference=reference):
                    before = {
                        s["id"] for s in spells.available_spells(breed, threshold - 1)
                    }
                    after = {s["id"] for s in spells.available_spells(breed, threshold)}
                    self.assertNotIn(reference, before)
                    self.assertIn(reference, after)
                    spells.validate_deck(
                        spells.encode_deck((), (reference,)), breed, threshold
                    )
                    with self.assertRaises(ValueError):
                        spells.validate_deck(
                            spells.encode_deck((), (reference,)), breed, threshold - 1
                        )

    def test_level_fifty_wire_owns_four_common_passives_without_acquisition_actives(
        self,
    ):
        body = spells.spell_inventory({"id": 6, "breed": 9, "level": 50})
        records = [
            struct.unpack_from(">qih", body, 2 + n * 14)
            for n in range(struct.unpack_from(">H", body)[0])
        ]
        references = {record[1] for record in records}
        self.assertTrue({4957, 4958, 4956, 5237} <= references)
        self.assertFalse({5146, 5145, 5144, 5621, 5622, 5623, 6327} & references)
        self.assertTrue(all(level == 50 for _, _, level in records))

    def test_native_common_passive_roots_have_complete_effect_closure(self):
        trees = json.loads(
            native_catalog.read_text(DATA_ROOT / "spell-effect-trees.json")
        )
        with native_catalog.open(DATA_ROOT / "native-spell-casting.json") as stream:
            casting = json.load(stream)["spells"]
        costs = json.loads(native_catalog.read_text(DATA_ROOT / "spell-costs.json"))[
            "spells"
        ]
        for reference, definition in spells.SPELLS.items():
            if definition["breed"] != -2:
                continue
            key = str(reference)
            self.assertIn(key, casting)
            self.assertEqual(costs[key]["levels"], casting[key]["costs"])
            pending = {
                effect
                for level in trees["spells"][key]["levels"]
                for effect in level[2]
            }
            seen = set()
            while pending:
                effect = pending.pop()
                if effect in seen:
                    continue
                seen.add(effect)
                row = trees["effects"][str(effect)]
                pending.update(row["children"])
