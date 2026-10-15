"""Native faW sgQ-only damage PC copied from its registered owner."""
import unittest

from wakfu_server.combat.combat_fake_fighter import fake_fighter_constructor
from wakfu_server.combat.combat_fake_fighter_owner_copy import (
    characteristics,
    constructor,
    damage_only_mask,
    install,
)


def definition(mask=2):
    return {
        "type": "FAKE_FIGHTER",
        "native_type_id": 15,
        "native_class": "bcQ",
        "raw_bdh": [-1, -1, 0, 0, 1, 1, 1, 1, 6, mask],
    }


class FakeFighterOwnerCopyTests(unittest.TestCase):
    def test_native_mask_two_copies_only_owner_pc21_into_damage_pc20(self):
        native = definition()
        owner = {21: 137, 1: 999, 20: 444}

        self.assertEqual(damage_only_mask(native), 2)
        receipt = constructor(native, owner)
        self.assertEqual(receipt["mask"], 2)
        self.assertEqual(receipt["owner_stats"], {"21": 137})
        self.assertEqual(receipt["characteristics"][20]["current"], 137)

        area = {}
        actual = install(area, native, owner)
        self.assertEqual(actual[20]["current"], 137)
        self.assertEqual(set(actual), {20})
        self.assertFalse(any(key.startswith("native_faw_hp_") for key in area))
        self.assertEqual(characteristics(area, native), actual)

    def test_area_constructor_creates_only_damage_pc_with_explicit_owner_authority(
        self,
    ):
        native = definition()
        with self.assertRaisesRegex(ValueError, "authority unavailable"):
            fake_fighter_constructor(native)
        constructor_row = fake_fighter_constructor(native, allow_hp=True)
        self.assertEqual(constructor_row["characteristic_ids"], (20,))
        self.assertEqual(constructor_row["visibility_obstacle"], True)

    def test_missing_owner_and_invalid_owner_values_are_rejected(self):
        native = definition()
        with self.assertRaisesRegex(ValueError, "owner snapshot"):
            constructor(native, None)
        for value in (True, 1.5, 1 << 32):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "owner characteristic"
            ):
                constructor(native, {21: value})

    def test_owner_additions_follow_native_mask_order_and_clamp(self):
        native = definition(mask=3)
        result = constructor(native, {20: 50_000, 21: 10_000})
        self.assertEqual(result["owner_stats"], {"20": 50_000, "21": 10_000})
        self.assertEqual(result["characteristics"][20]["current"], 50_000)

    def test_mutable_damage_pc_stays_bounded_and_receipt_or_hp_forgery_rejects(self):
        native = definition()
        area = {}
        install(area, native, {21: 10})
        # Runtime PA effects may mutate current after construction.
        area["native_faw_damage_current"] = 11
        self.assertEqual(characteristics(area, native)[20]["current"], 11)
        area["native_faw_damage_current"] = 50_001
        with self.assertRaisesRegex(ValueError, "authority"):
            characteristics(area, native)

        area = {}
        install(area, native, {21: 10})
        area["native_faw_damage_only_constructor"]["characteristics"][20][
            "current"
        ] = 12
        with self.assertRaisesRegex(ValueError, "authority"):
            characteristics(area, native)

        area = {}
        install(area, native, {21: 10})
        area["native_faw_hp_constructor"] = {}
        with self.assertRaisesRegex(ValueError, "authority"):
            characteristics(area, native)

    def test_unrecognized_faw_prototype_contract_stays_rejected(self):
        native = definition()
        native["native_class"] = "unknown"
        with self.assertRaisesRegex(ValueError, "prototype"):
            damage_only_mask(native)


if __name__ == "__main__":
    unittest.main()
