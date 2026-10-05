import unittest
from wakfu_server.equipment import validate_sheet, RULES
from wakfu_server.wire import proto_field


class EquipmentTests(unittest.TestCase):
    def test_native_simple_owned_item_and_unequipped_sheet(self):
        rule = RULES[2021]
        self.assertEqual((rule["minimum_level"], rule["slots"]), (6, [4]))
        char = dict(
            id=1,
            level=6,
            inventory_items=[
                dict(uid=1000, character_id=1, reference=2021, quantity=1)
            ],
        )
        blob = proto_field(10, proto_field(8, 1000) + proto_field(16, 4))
        self.assertEqual(validate_sheet(char, blob), [dict(uid=1000, slot=4)])
        self.assertEqual(validate_sheet(char, proto_field(424, (1 << 64) - 1)), [])
        for bad in (
            {**char, "level": 5},
            {**char, "inventory_items": []},
            {
                **char,
                "inventory_items": [{**char["inventory_items"][0], "character_id": 2}],
            },
            {
                **char,
                "inventory_items": [{**char["inventory_items"][0], "quantity": 2}],
            },
        ):
            with self.assertRaises(ValueError):
                validate_sheet(bad, blob)
        with self.assertRaises(ValueError):
            validate_sheet(char, blob + blob)
        with self.assertRaises(ValueError):
            validate_sheet(
                char, proto_field(10, proto_field(8, 1000) + proto_field(16, 7))
            )

    def test_proven_conditional_and_extra_slot_items_preserve_real_uid(self):
        for reference in (12, 2022):
            rule = RULES[reference]
            char = dict(
                id=1,
                level=200,
                inventory_items=[
                    dict(uid=1000, character_id=1, reference=reference, quantity=1)
                ],
            )
            blob = proto_field(
                10, proto_field(8, 1000) + proto_field(16, rule["slots"][0])
            )
            self.assertEqual(
                validate_sheet(char, blob), [dict(uid=1000, slot=rule["slots"][0])]
            )
