import unittest
from functools import partial
from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.combat_inventory_date_conditions import (
    owned_item_quantity,
    calendar_milliseconds,
)


class InventoryDateConditionsTests(unittest.TestCase):
    def test_native_promotional_guard_has_actual_item_and_date_boundaries(self):
        criterion = (
            "GetItemQuantity(32870) >= 1 and "
            "GetDate() >= GetDate(06,01,2026,09,59,59) and "
            "GetDate() < GetDate(07,07,2026,10,00,00)"
        )
        start = calendar_milliseconds((6, 1, 2026, 9, 59, 59))
        end = calendar_milliseconds((7, 7, 2026, 10, 0, 0))
        item = {"uid": 1, "reference": 32870, "quantity": 1}

        def check(items, now):
            return evaluate_condition(
                criterion,
                ConditionContext(
                    {},
                    world_property_now_ms=now,
                    item_quantity_query=partial(owned_item_quantity, items),
                ),
            )

        self.assertFalse(check([], start))
        self.assertFalse(check([item], start - 1))
        self.assertTrue(check([item], start))
        self.assertTrue(check([item], end - 1))
        self.assertFalse(check([item], end))

    def test_inventory_counts_stacks_equipped_items_and_native_reference_narrowing(
        self,
    ):
        items = [
            {"uid": 1, "reference": 4, "quantity": 3, "slot": None},
            {"uid": 2, "reference": 4, "quantity": 1, "slot": 0},
        ]
        self.assertEqual(owned_item_quantity(items, (4,)), 4)
        self.assertEqual(owned_item_quantity(items, (4, 4)), 8)
        self.assertEqual(owned_item_quantity(items, (2**32 + 4,)), 4)
        self.assertEqual(owned_item_quantity(items, (5,)), 0)
        with self.assertRaises(ValueError):
            owned_item_quantity(None, (4,))
        with self.assertRaises(ValueError):
            owned_item_quantity(items + [items[0]], (4,))

    def test_unknown_clock_inventory_and_calendar_do_not_become_false(self):
        for expression in (
            "GetDate()>0",
            "GetItemQuantity(1)>0",
            "GetDate(29,2,2025,0,0,0)>0",
            "GetDate(1,1,1500,0,0,0)>0",
        ):
            with self.subTest(expression=expression), self.assertRaises(
                UnknownCondition
            ):
                evaluate_condition(expression, ConditionContext({}))

    def test_decimal_normalization_preserves_strings_and_rejects_spaced_numbers(self):
        self.assertTrue(evaluate_condition("06 == 6 and 09 == 9", ConditionContext({})))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("0 6 == 6", ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition('GetDate("06",1,2026,0,0,0)>0', ConditionContext({}))

    def test_utc_calendar_matches_original_probe(self):
        self.assertEqual(calendar_milliseconds((6, 1, 2026, 9, 59, 59)), 1767693599000)
        self.assertEqual(
            calendar_milliseconds((2**32 + 6, 1, 2026, 9, 59, 59)), 1767693599000
        )

    def test_current_fighter_identity_is_distinct_from_effect_caster(self):
        self.assertTrue(
            evaluate_condition(
                "GetCurrentFighterId() == -7",
                ConditionContext({}, current_fighter_id=-7),
            )
        )
        self.assertTrue(
            evaluate_condition(
                "GetCurrentFighterId() == 0", ConditionContext({}, current_fighter_id=0)
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetCurrentFighterId() == 0", ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "GetCurrentFighterId(1) == 0",
                ConditionContext({}, current_fighter_id=0),
            )


if __name__ == "__main__":
    unittest.main()
