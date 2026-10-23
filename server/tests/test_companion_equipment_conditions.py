import unittest

from wakfu_server.equipment import RULES, validate_sheet
from wakfu_server.equipment_conditions import catalog, evaluate
from wakfu_server.wire import proto_field


class CompanionEquipmentConditionTests(unittest.TestCase):
    def context(self, level):
        return {"actor_kind": "native_companion_npc", "level": level}

    def test_native_level_predicates_use_companion_effective_npc_level(self):
        item = {"uid": 1, "reference": 17259}
        owned = {1: item}
        selected = [{"uid": 1, "slot": 0}]
        criterion = catalog()["17259"]["EQUIP"]
        self.assertEqual(criterion, "GetLevel() >= 125")

        for level, expected in ((124, False), (125, True)):
            with self.subTest(level=level):
                self.assertEqual(
                    evaluate(
                        criterion,
                        item=item,
                        selected=selected,
                        owned=owned,
                        criterion_context=self.context(level),
                    ),
                    expected,
                )

        with self.assertRaisesRegex(ValueError, "not implemented"):
            evaluate(criterion, item=item, selected=selected, owned=owned)
        with self.assertRaisesRegex(ValueError, "explicit native companion"):
            evaluate(
                criterion,
                item=item,
                selected=selected,
                owned=owned,
                criterion_context={"actor_kind": "unverified_actor", "level": 125},
            )

    def test_native_real_level_condition_uses_companion_actor_level(self):
        item = {"uid": 1, "reference": 14891}
        owned = {1: item}
        selected = [{"uid": 1, "slot": 4}]
        criterion = catalog()["14891"]["EQUIP"]
        self.assertEqual(criterion.strip(), "GetRealLevel() <= 30")
        for level, expected in ((30, True), (31, False)):
            with self.subTest(level=level):
                self.assertEqual(
                    evaluate(
                        criterion,
                        item=item,
                        selected=selected,
                        owned=owned,
                        criterion_context=self.context(level),
                    ),
                    expected,
                )
        with self.assertRaisesRegex(ValueError, "not implemented"):
            evaluate(criterion, item=item, selected=selected, owned=owned)

    def test_has_equipment_id_checks_companion_equipped_units_only(self):
        candidate = {"uid": 1, "reference": 26494}
        prohibited = {"uid": 2, "reference": 26575}
        owned = {1: candidate, 2: prohibited}
        criterion = catalog()["26494"]["EQUIP"]
        self.assertEqual(criterion, "HasEquipmentId(26575)")

        self.assertFalse(
            evaluate(
                criterion,
                item=candidate,
                selected=[{"uid": 1, "slot": 15}],
                owned=owned,
                criterion_context=self.context(200),
            )
        )
        self.assertTrue(
            evaluate(
                criterion,
                item=candidate,
                selected=[{"uid": 1, "slot": 15}, {"uid": 2, "slot": 7}],
                owned=owned,
                criterion_context=self.context(200),
            )
        )
        with self.assertRaisesRegex(ValueError, "not implemented"):
            evaluate(criterion, item=candidate, selected=[], owned=owned)

    def test_get_equipment_reads_the_explicit_companion_sheet(self):
        item = {"uid": 1, "reference": 26494}
        replaced = {"uid": 2, "reference": 26575}
        current = {"uid": 3, "reference": 2022}
        owned = {1: item, 2: replaced, 3: current}
        context = self.context(200)

        self.assertTrue(
            evaluate(
                "GetEquipment(7) == 26575",
                item=item,
                selected=[{"uid": 1, "slot": 15}, {"uid": 2, "slot": 7}],
                current_equipped=[{"uid": 3, "slot": 7}],
                owned=owned,
                criterion_context=context,
            )
        )
        self.assertTrue(
            evaluate(
                "GetEquipment(7) == 2022",
                item=item,
                selected=[{"uid": 1, "slot": 15}],
                current_equipped=[{"uid": 3, "slot": 7}],
                owned=owned,
                criterion_context=context,
            )
        )
        self.assertTrue(
            evaluate(
                "GetEquipment(8) == -1",
                item=item,
                selected=[{"uid": 1, "slot": 15}],
                owned=owned,
                criterion_context=context,
            )
        )
        with self.assertRaisesRegex(ValueError, "not implemented"):
            evaluate("GetEquipment(7) == 26575", item=item, selected=[], owned=owned)

    def test_native_empty_equipment_emblems_read_companion_physical_slots(self):
        owned = {
            1: {"uid": 1, "reference": 29573},
            2: {"uid": 2, "reference": 13601},
        }
        selected_empty = [{"uid": 1, "slot": 17}]
        selected_occupied = [*selected_empty, {"uid": 2, "slot": 0}]

        for reference in (29573, 29578):
            criterion = catalog()[str(reference)]["EQUIP"]
            with self.subTest(reference=reference):
                self.assertIn("GetEquipment(0) == -1", criterion)
                self.assertTrue(
                    evaluate(
                        criterion,
                        item=owned[1],
                        selected=selected_empty,
                        owned=owned,
                        criterion_context=self.context(200),
                    )
                )
                self.assertFalse(
                    evaluate(
                        criterion,
                        item=owned[1],
                        selected=selected_occupied,
                        owned=owned,
                        criterion_context=self.context(200),
                    )
                )

    def test_companion_sheet_validation_applies_native_level_boundary_atomically(self):
        item = {"uid": 11, "character_id": 7, "quantity": 1, "reference": 17259}
        slot = RULES[17259]["slots"][0]
        sheet = proto_field(10, proto_field(8, item["uid"]) + proto_field(16, slot))
        pseudo = {
            "id": 7,
            "level": 125,
            "effective_level": 125,
            "inventory_items": [item],
        }

        with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
            validate_sheet(pseudo, sheet, criterion_context=self.context(124))
        self.assertEqual(
            validate_sheet(pseudo, sheet, criterion_context=self.context(125)),
            [{"uid": 11, "slot": slot}],
        )


if __name__ == "__main__":
    unittest.main()
