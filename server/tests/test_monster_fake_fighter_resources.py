"""Pure faW HP constructor differential checks against installed Java."""
import json
from pathlib import Path
import unittest

from wakfu_server.combat_fake_fighter_resources import (
    HP_CHARACTERISTIC,
    SOURCE,
    fake_fighter_hp_resources,
)


def definition(base=8, per_level=0):
    return dict(
        type="FAKE_FIGHTER",
        native_type_id=15,
        native_class="bcQ",
        raw_bdh=[0, base, per_level, 1, 1, 1, 0, 1, 0, -1],
    )


class FakeFighterResourcesTests(unittest.TestCase):
    def test_installed_native_hp_differential_cases(self):
        fixture = Path(__file__).parent / "fixtures/monster_faw_hp_native.json"
        rows = json.loads(fixture.read_text())["cases"]
        self.assertEqual(len(rows), 60)
        for row in rows:
            with self.subTest(
                base=row["base"], per=row["per_level"], level=row["level"]
            ):
                actual = fake_fighter_hp_resources(
                    definition(row["base"], row["per_level"]), row["level"]
                )
                self.assertEqual(actual["source"], SOURCE)
                self.assertEqual(actual["characteristics"], {row["hp_id"]: row["hp"]})
                self.assertFalse(row["damage_present"])

    def test_actual_area566_constructs_eight_hp_only(self):
        actual = fake_fighter_hp_resources(definition(), 141)
        self.assertEqual(set(actual["characteristics"]), {HP_CHARACTERISTIC})
        self.assertEqual(actual["characteristics"][HP_CHARACTERISTIC]["current"], 8)
        self.assertEqual(actual["characteristics"][HP_CHARACTERISTIC]["maximum"], 8)

    def test_unknown_prototype_level_and_pc_branches_stay_rejected(self):
        for field, value in (
            ("type", "TRAP"),
            ("native_type_id", 3),
            ("native_class", "guess"),
        ):
            row = definition()
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                fake_fighter_hp_resources(row, 141)
        for level in (None, True, -1, 32768, 1.0):
            with self.subTest(level=level), self.assertRaises(ValueError):
                fake_fighter_hp_resources(definition(), level)
        for base, mask in ((-1, -1), (100, 0), (100, 128)):
            row = definition(base)
            row["raw_bdh"][9] = mask
            with self.subTest(base=base, mask=mask), self.assertRaises(ValueError):
                fake_fighter_hp_resources(row, 141)
        row = definition()
        row["raw_bdh"] += [29, 100, 100, 100]
        with self.assertRaises(ValueError):
            fake_fighter_hp_resources(row, 141)

    def test_construction_does_not_mutate_definition_or_enable_runtime(self):
        from wakfu_server.combat_fake_fighter import fake_fighter_constructor

        row = definition()
        before = json.dumps(row)
        fake_fighter_hp_resources(row, 141)
        self.assertEqual(json.dumps(row), before)
        with self.assertRaisesRegex(ValueError, "authority unavailable"):
            fake_fighter_constructor(row)
