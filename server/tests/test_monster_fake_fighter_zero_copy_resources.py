"""Installed faW HP+sgQ constructor, explicitly zero owner-copy mask."""
import json
from pathlib import Path
import unittest

from wakfu_server.combat_fake_fighter_resources import (
    DAMAGE_SOURCE,
    fake_fighter_zero_copy_resources,
    fake_fighter_hp_resources,
)


def definition(base=100, per_level=0):
    return dict(
        type="FAKE_FIGHTER",
        native_class="bcQ",
        native_type_id=15,
        raw_bdh=[0, base, per_level, 0, 0, 0, 1, 1, 0, 0],
    )


class FakeFighterZeroCopyResourcesTests(unittest.TestCase):
    def test_installed_native_pa_differential_cases(self):
        rows = json.loads(
            (
                Path(__file__).parent / "fixtures/monster_faw_hp_damage_native.json"
            ).read_text()
        )["cases"]
        self.assertEqual(len(rows), 48)
        for row in rows:
            with self.subTest(
                base=row["base"], per=row["per_level"], level=row["level"]
            ):
                actual = fake_fighter_zero_copy_resources(
                    definition(row["base"], row["per_level"]), row["level"]
                )
                self.assertEqual(actual["source"], DAMAGE_SOURCE)
                self.assertEqual(
                    actual["characteristics"],
                    {row["hp_id"]: row["hp"], row["damage_id"]: row["damage"]},
                )

    def test_real_areas_have_hp100_and_present_zero_damage_pc(self):
        actual = fake_fighter_zero_copy_resources(definition(), 55)
        self.assertEqual(actual["characteristics"][1]["current"], 100)
        self.assertEqual(
            actual["characteristics"][20],
            dict(
                current=0,
                maximum=50000,
                minimum=-5000,
                absolute_minimum=-5000,
                absolute_maximum=50000,
            ),
        )
        with self.assertRaises(ValueError):
            fake_fighter_hp_resources(definition(), 55)

    def test_owner_copy_and_optional_dynamic_characteristics_stay_rejected(self):
        for mask in (-1, 1, 2, 4, 8, 16, 32, 64, 127, 128):
            row = definition()
            row["raw_bdh"][9] = mask
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                fake_fighter_zero_copy_resources(row, 55)
        row = definition()
        row["raw_bdh"] += [29, 100, 100, 100]
        with self.assertRaises(ValueError):
            fake_fighter_zero_copy_resources(row, 55)
