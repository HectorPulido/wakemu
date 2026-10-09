"""Source-qualified item PL identity and native encounter order regression."""
import unittest
from wakfu_server.combat_copied_equipment_plan import SOURCE, copied_equipment_plan


class CopiedEquipmentPlanTests(unittest.TestCase):
    def catalog(self):
        roots = [
            dict(
                ordinal=index,
                reference=reference,
                effect_class=1066,
                parameters=[1.0, 0.0],
                metadata={},
            )
            for index, reference in enumerate((91, 4, 91))
        ]
        return dict(
            producer=SOURCE,
            complete=True,
            definition_count=1,
            definitions={
                "7": dict(
                    reference=7,
                    container_type=12,
                    fresh_container_level=20,
                    ordered_effects=roots,
                )
            },
        )

    def test_item_pl_and_duplicate_encounter_order_are_preserved(self):
        catalog = self.catalog()
        plan = copied_equipment_plan(7, catalog)
        self.assertEqual([root["reference"] for root in plan["roots"]], [91, 4, 91])
        self.assertEqual(
            plan["native_retained_container"],
            dict(
                present=True,
                type=12,
                id=7,
                level=20,
                is_spell=False,
                native_kind="item",
            ),
        )
        plan["roots"][0]["parameters"][0] = 9
        self.assertEqual(
            catalog["definitions"]["7"]["ordered_effects"][0]["parameters"][0], 1
        )

    def test_only_complete_table_proves_native_missing_return(self):
        self.assertEqual(
            copied_equipment_plan(8, self.catalog())["status"],
            "missing_definition_return",
        )
        catalog = self.catalog()
        catalog["complete"] = False
        with self.assertRaises(ValueError):
            copied_equipment_plan(8, catalog)
        self.assertEqual(copied_equipment_plan(0, None)["status"], "zero_return")

    def test_corrupt_order_and_container_do_not_authorize_application(self):
        for key, value in (("container_type", 1), ("fresh_container_level", None)):
            catalog = self.catalog()
            catalog["definitions"]["7"][key] = value
            with self.assertRaises(ValueError):
                copied_equipment_plan(7, catalog)
        catalog = self.catalog()
        catalog["definitions"]["7"]["ordered_effects"][0]["ordinal"] = 1
        with self.assertRaises(ValueError):
            copied_equipment_plan(7, catalog)
