"""Native 2636 equipment start-characteristic contract qualification."""
import unittest


class CombatEquipmentStartCharacteristicTests(unittest.TestCase):
    def test_four_native_2636_sources_qualify_individually(self):
        from wakfu_server.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )
        from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
        from wakfu_server.combat_copied_equipment_execution import (
            equipment_effect_definitions,
        )
        from wakfu_server.combat_owned_equipment import (
            compiled_with_sources,
            ordinary_turn_state_contract,
        )
        from wakfu_server.combat_equipment_passive_completeness import (
            unplanned_passive_effect_ids,
        )
        from wakfu_server.combat_server_spell import compiled_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.equipment_stats import CATALOG

        native = native_copied_equipment_catalog()
        compiled = compiled_runtime_catalog()
        registry = characteristic_registry()
        reasons = {}
        for reference in (18091, 23215, 27297, 27298):
            plan = copied_equipment_plan(reference, native)
            roots = [
                row
                for row in plan["roots"]
                if row["effect_class"] == 304
                and row["variant"] == 0
                and row["metadata"]["native_active_effect"] is False
            ]
            source = dict(
                uid=1000 + reference,
                reference=reference,
                source_reference=reference,
                attachment_field=None,
                roots=tuple(row["reference"] for row in roots),
                effects=equipment_effect_definitions(dict(roots=roots)),
                native_retained_container=plan["native_retained_container"],
            )
            source["unplanned_passive_effect_ids"] = unplanned_passive_effect_ids(
                reference, plan, source["roots"], templates=CATALOG
            )
            extended = compiled_with_sources(compiled, [source])
            reasons[reference] = ordinary_turn_state_contract(
                source, extended, registry
            )
        self.assertEqual(reasons, {reference: None for reference in reasons}, reasons)


if __name__ == "__main__":
    unittest.main()
