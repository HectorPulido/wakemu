import unittest
from wakfu_server.equipment import validate_sheet
from wakfu_server.equipment_conditions import catalog, evaluate
from wakfu_server.wire import proto_field


class EquipmentConditionsTests(unittest.TestCase):
    def character(self):
        return {
            "id": 7,
            "level": 20,
            "inventory_items": [
                {"uid": 101, "character_id": 7, "quantity": 1, "reference": 2022},
                {"uid": 102, "character_id": 7, "quantity": 1, "reference": 2022},
            ],
        }

    def sheet(self, rows):
        return b"".join(
            proto_field(10, proto_field(8, u) + proto_field(16, s)) for u, s in rows
        )

    def test_native_ring_condition_single_ring_ignores_bag_duplicate(self):
        from wakfu_server.equipment import RULES

        self.assertEqual(catalog()["2022"]["EQUIP"], "not HasAnotherSameEquipment()")
        slot = RULES[2022]["slots"][0]
        self.assertEqual(
            validate_sheet(self.character(), self.sheet([(101, slot)])),
            [{"uid": 101, "slot": slot}],
        )

    def test_native_different_uid_same_reference_equipped_rejected(self):
        from wakfu_server.equipment import RULES

        slots = RULES[2022]["slots"]
        self.assertGreaterEqual(len(slots), 2)
        with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
            validate_sheet(
                self.character(), self.sheet([(101, slots[0]), (102, slots[1])])
            )

    def test_same_uid_clone_is_not_another_reference_and_unknown_is_rejected(self):
        item = self.character()["inventory_items"][0]
        owned = {101: item}
        self.assertFalse(
            evaluate(
                "HasAnotherSameEquipment()",
                item=item,
                selected=[{"uid": 101}, {"uid": 101}],
                owned=owned,
            )
        )
        with self.assertRaisesRegex(ValueError, "not implemented"):
            evaluate(
                "True or UnknownEquipmentPredicate()",
                item=item,
                selected=[],
                owned=owned,
            )

    def test_catalog_covers_every_equipment_rule(self):
        from wakfu_server.equipment import RULES

        self.assertEqual(set(map(int, catalog())), set(RULES))

    def test_two_hand_weapon_preserves_primary_uid_once_and_reserves_secondary(self):
        from wakfu_server.equipment import RULES

        character = {
            "id": 7,
            "level": 20,
            "inventory_items": [
                {"uid": 103, "character_id": 7, "quantity": 1, "reference": 2027}
            ],
        }
        self.assertEqual(RULES[2027]["occupied_slots"], [16])
        self.assertEqual(
            validate_sheet(character, self.sheet([(103, 15)])),
            [{"uid": 103, "slot": 15}],
        )
        offhand = next(
            ref
            for ref, rule in RULES.items()
            if 16 in rule["slots"]
            and rule["minimum_level"] <= 20
            and not rule["has_conditions"]
        )
        character["inventory_items"].append(
            {"uid": 104, "character_id": 7, "quantity": 1, "reference": offhand}
        )
        for rows in ([(103, 15), (104, 16)], [(104, 16), (103, 15)]):
            with self.assertRaisesRegex(ValueError, "Duplicate equipment"):
                validate_sheet(character, self.sheet(rows))

    def test_native_two_hand_passive_bonuses_applied_once(self):
        from wakfu_server.equipment_stats import bonuses

        character = {
            "id": 7,
            "breed": 11,
            "level": 20,
            "inventory_items": [
                {"uid": 103, "character_id": 7, "quantity": 1, "reference": 2027}
            ],
        }
        character["builds"] = {0: {"equipment": self.sheet([(103, 15)]).hex()}}
        result = bonuses(character)
        self.assertEqual(result["equipped_uids"], [103])
        # Native installed2027 effects184060/184061/184062: HP11, ferocity2, mastery14.
        self.assertEqual(
            {stat: result["stats"][stat] for stat in (1, 9, 20)}, {1: 11, 9: 2, 20: 14}
        )
