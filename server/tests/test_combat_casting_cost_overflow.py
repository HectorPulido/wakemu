"""Native fyF.g performs signed Java additions before its ordinary-cost clamp."""
import unittest
from unittest.mock import patch

from wakfu_server.combat_native_spell_casting import definition


class NativeCastingCostOverflowTests(unittest.TestCase):
    def cost(self, base, modifiers, categories=(1, 2)):
        record = dict(
            costs=[[base, 0, 0]],
            levels=[[0, 1, []]],
            conditional=[],
            categories=categories,
            line_of_sight=True,
            linear=False,
            free_cell=False,
            range_modifiable=False,
            path_option=False,
            diagonal=False,
            linear_path=False,
            allow_self=False,
            forbid_QI_P=False,
            cast_criterion_raw=None,
            cast_criterion_native_present=False,
        )
        with patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={"1": record},
        ):
            return definition(1, 1, None, modifiers)["costs"]["ap"]

    def test_positive_cost_overflow_wraps_before_clamping(self):
        self.assertEqual(self.cost(2147483647, {1: 1}), 0)

    def test_category_accumulation_wraps_as_native_enumset_sum(self):
        self.assertEqual(self.cost(3, {1: 2147483647, 2: 2147483647}), 1)

    def test_negative_sum_overflow_can_produce_positive_cost(self):
        self.assertEqual(self.cost(-2147483647, {1: -2}), 2147483647)

    def test_duplicate_categories_are_not_applied_twice(self):
        self.assertEqual(self.cost(3, {1: 2}, categories=(1, 1)), 5)
