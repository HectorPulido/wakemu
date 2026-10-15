"""Indexed native spell ownership preserves ordering and level boundaries."""
import unittest
from unittest.mock import patch
from wakfu_server import spells


class SpellAvailabilityIndexTests(unittest.TestCase):
    def test_every_native_breed_and_unlock_boundary_matches_full_scan(self):
        records = tuple(spells.SPELLS.values())
        breeds = {r["breed"] for r in records} | {999999}
        levels = {1, 230} | {
            max(1, r["unlock_level"] + delta) for r in records for delta in (-1, 0, 1)
        }
        for breed in breeds:
            for level in levels:
                expected = [
                    r
                    for r in records
                    if (
                        r["breed"] == breed
                        or (r["breed"] == -2 and r["kind"] == "passive")
                    )
                    and r["unlock_level"] <= level
                ]
                self.assertEqual(
                    spells.available_spells(breed, level), expected, (breed, level)
                )

    def test_replaced_catalog_and_fresh_result_list(self):
        before = spells.available_spells(8, 1)
        original = list(before)
        before.clear()
        self.assertEqual(spells.available_spells(8, 1), original)
        with patch.object(spells, "SPELLS", {}):
            self.assertEqual(spells.available_spells(8, 1), [])
        self.assertEqual(spells.available_spells(8, 1), original)

    def test_invalid_owner_arguments_remain_rejected(self):
        for breed, level in [(True, 1), (8, True), (8, 0), (8, 1.5), ("8", 1)]:
            with self.assertRaises(ValueError):
                spells.available_spells(breed, level)
