"""Actual PL reference and native enum PCs, including proved null presence."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_combat_trap_area as trap_fixture
import test_combat_fake_fighter_area as area_fixture
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_spell_element_pc import spell_element_pc, native_spell_elements
from wakfu_server.combat_area_damage_snapshot import copy_area_damage_snapshot
from wakfu_server.combat_trap_area import verified_trap_characteristics


class AreaSpellElementPCTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(
            (
                Path(__file__).parent
                / "fixtures/monster_spell_element_damage_pcs_native.json"
            ).read_text()
        )
        self.scope = patch(
            "wakfu_server.combat_spell_element_pc.native_spell_element_damage_pcs",
            return_value=self.catalog,
        )
        self.scope.start()
        self.addCleanup(self.scope.stop)

    def container(self, reference):
        identity = (reference << 16) | 80
        return (
            dict(
                container_present=True,
                container_type=11,
                container_is_spell=True,
                container_id=identity,
            ),
            identity,
        )

    def test_installed_enum_differential_uses_actual_spell_metadata(self):
        spells = native_spell_elements()
        for key, expected in self.catalog["elements"].items():
            reference = next(
                int(ref)
                for ref, row in spells.items()
                if row["native_element"] == int(key)
            )
            with self.subTest(element=key, reference=reference):
                operand = spell_element_pc(*self.container(reference))
                self.assertEqual(operand.characteristic_id, expected["damage_stat"])
                self.assertEqual(operand.element_name, expected["element_name"])

    def test_corbot_actual_physical_pl_has_null_pc_and_keeps_general_damage(self):
        row, definition = trap_fixture.NativeTrapAreaTests().fixture(properties=())
        operand = spell_element_pc(*self.container(4881))
        self.assertIsNone(operand.characteristic_id)
        self.assertTrue(
            copy_area_damage_snapshot(
                row,
                definition,
                source_stats={20: 100, 23: 900},
                container_type=11,
                spell_element_provider=lambda: operand,
            )
        )
        self.assertEqual(verified_trap_characteristics(row, definition)[20], 100)

    def test_elemental_copy_uses_actual_container_and_native_ordered_delta(self):
        reference = next(
            int(ref)
            for ref, row in native_spell_elements().items()
            if row["native_element"] == 3
        )
        row, definition = trap_fixture.NativeTrapAreaTests().fixture(properties=())
        operand = spell_element_pc(*self.container(reference))
        self.assertEqual(operand.characteristic_id, 23)
        copy_area_damage_snapshot(
            row,
            definition,
            source_stats={20: 100, 23: 37},
            container_type=11,
            spell_element_provider=lambda: operand,
        )
        self.assertEqual(verified_trap_characteristics(row, definition)[20], 137)

    def test_missing_metadata_and_unproved_null_are_not_absence(self):
        descriptor, identity = self.container(4881)
        for mutation in (
            {"container_id": identity + 1},
            {"container_present": False},
            {"container_type": 25},
            {"container_is_spell": False},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                spell_element_pc(dict(descriptor, **mutation), identity)
        self.catalog["null_pc_present"] = None
        with self.assertRaisesRegex(ValueError, "null-PC"):
            spell_element_pc(descriptor, identity)
        self.catalog["null_pc_present"] = False
        del self.catalog["elements"]["0"]["damage_stat"]
        with self.assertRaisesRegex(ValueError, "authority"):
            spell_element_pc(descriptor, identity)

    def test_non_damage_areas_do_not_demand_spell_operand(self):
        def unavailable():
            self.fail("No sgQ means native eYW never reads fyG element")

        self.assertFalse(
            copy_area_damage_snapshot(
                {"native_area_contract": "faN"},
                {},
                container_type=11,
                spell_element_provider=unavailable,
            )
        )

    def test_actual_area_handler_passes_retained_pl_identity_to_lazy_producer(self):
        fight, handler, _, _ = area_fixture.NativeFakeFighterAreaTests().create()
        fight.actors[7].effect_stats = {20: 100, 23: 900}
        actual_pl = self.container(4881)
        handler.container = lambda invocation: actual_pl
        self.assertTrue(
            handler(
                {"effect_class": 308},
                {"parameters": [1000, 80]},
                EffectInvocation(201, 80, 7, None, (2, 3, 0)),
            )
        )
        row = fight.native_effect_areas[901]
        self.assertEqual(
            verified_trap_characteristics(row, native_effect_areas()["1000"])[20], 100
        )
