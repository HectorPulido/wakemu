import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_character_copy_equipment import copied_equipment_source
from wakfu_server.combat_runtime_adapter import NativeActorAuthority


def authority(selected):
    return NativeActorAuthority(
        targeting={},
        is_player=True,
        deck_spell_ids=frozenset(),
        excluded_deck_spell_ids=frozenset(),
        is_carried=False,
        breed_id=14,
        summon_count=0,
        summon_counts_by_breed={},
        occupant_blocks=True,
        native_selected_cosmetics=selected,
    )


class CopyEquipmentTests(unittest.TestCase):
    def test_actual_zero_operand_is_noop_not_copied_cosmetic_state(self):
        source = authority({7: 0})
        result = copied_equipment_source(source, 7)
        self.assertEqual(
            result,
            dict(producer="big.copy.eGj.PJ.zero_return", source_actor_id=7, dsK=0),
        )
        self.assertEqual(source.native_selected_cosmetics, {7: 0})

    def test_missing_operand_remains_unknown(self):
        for selected in (None, {}, {7: False}):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                copied_equipment_source(authority(selected), 7)

    def test_nonzero_requires_a_complete_native_definition_table(self):
        from wakfu_server.combat_copied_equipment_plan import SOURCE

        with patch(
            "wakfu_server.combat_character_copy_equipment.native_copied_equipment_catalog",
            return_value=dict(producer=SOURCE, complete=False, definitions={}),
        ), self.assertRaisesRegex(ValueError, "complete native copied equipment"):
            copied_equipment_source(authority({7: 3}), 7)

    def test_actual_positive_completed_catalog_preserves_native_plan(self):
        result = copied_equipment_source(authority({7: 12}), 7)
        self.assertEqual(result["dsK"], 12)
        self.assertEqual(result["native_plan"]["native_retained_container"]["type"], 12)
        self.assertEqual(result["native_plan"]["native_retained_container"]["id"], 12)
        self.assertEqual(
            result["native_plan"]["native_retained_container"]["level"], 60
        )
        self.assertTrue(result["native_plan"]["roots"])

    def test_untyped_verified_flag_cannot_authorize_source(self):
        with self.assertRaisesRegex(ValueError, "typed copied source"):
            copied_equipment_source(
                SimpleNamespace(verified=True, native_selected_cosmetics={7: 0}), 7
            )
