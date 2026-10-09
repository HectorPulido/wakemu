import unittest
from wakfu_server.combat_area_damage_snapshot import copy_area_damage_snapshot


class NativeAreaDamageSnapshotTests(unittest.TestCase):
    def test_plain_faV_domains_do_not_acquire_invented_damage_stats(self):
        for contract in ("faY", "faZ", "faN", "faX", "faU"):
            with self.subTest(contract=contract):
                row = {"native_area_contract": contract}
                self.assertFalse(copy_area_damage_snapshot(row, {}))
                self.assertEqual(
                    row["native_eyw_damage_copy"], "eYW.fQG.skipped_no_sgQ"
                )
                self.assertNotIn("effect_stats", row)

    def test_unknown_constructor_is_not_a_noop_proof(self):
        row = {"native_area_contract": "unverified-trap"}
        with self.assertRaises(ValueError):
            copy_area_damage_snapshot(row, {})
        self.assertNotIn("native_eyw_damage_copy", row)

    def test_fake_fighter_requires_actual_constructor_before_guard(self):
        row = {"native_area_contract": "faW"}
        with self.assertRaises(ValueError):
            copy_area_damage_snapshot(row, {})
        self.assertNotIn("native_eyw_damage_copy", row)

    def test_wall_requires_actual_constructor_before_guard(self):
        row = {"native_area_contract": "fbd"}
        with self.assertRaisesRegex(ValueError, "constructor level"):
            copy_area_damage_snapshot(row, {})
        self.assertNotIn("native_eyw_damage_copy", row)

    def test_wall_passes_captured_level_to_constructor(self):
        from unittest.mock import patch

        row = {
            "native_area_contract": "fbd",
            "level": 37,
            "native_wall_constructor": {"hp": 74},
        }
        definition = {"native": "fixture"}
        with patch(
            "wakfu_server.combat_wall_area.wall_constructor", return_value={"hp": 74}
        ) as constructor:
            self.assertFalse(copy_area_damage_snapshot(row, definition))
        constructor.assert_called_once_with(definition, 37)
