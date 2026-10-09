import unittest

from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_cosmetic_conditions import (
    NativeCosmeticState,
    active_cosmetic_id,
    has_active_cosmetic,
)


class CosmeticConditionTests(unittest.TestCase):
    def test_selected_esU_values_and_active_eSP_membership(self):
        state = NativeCosmeticState(
            True,
            {3: 91, 4: 0, 5: (701, 702), 6: 0, 7: 42},
            {9: (991, 992)},
        )
        self.assertEqual(active_cosmetic_id(state, 3), 91)
        self.assertEqual(active_cosmetic_id(state, 5), 701)
        self.assertEqual(active_cosmetic_id(state, 7), 42)
        self.assertEqual(active_cosmetic_id(state, 9), 991)
        self.assertTrue(has_active_cosmetic(state, 9, 992))
        self.assertFalse(has_active_cosmetic(state, 9, 993))

    def test_known_empty_and_nonfighter_native_results(self):
        empty = NativeCosmeticState(True, {3: 0, 4: 0, 5: (), 6: 0, 7: 0}, {})
        self.assertEqual(active_cosmetic_id(empty, 5), 0)
        self.assertEqual(active_cosmetic_id(empty, 13), 0)
        self.assertEqual(
            active_cosmetic_id(NativeCosmeticState(True, None, None), 99), 0
        )
        self.assertFalse(has_active_cosmetic(empty, 13, 1234))
        self.assertFalse(
            has_active_cosmetic(NativeCosmeticState(True, None, None), 99, 1234)
        )
        nonfighter = NativeCosmeticState(False, None, None)
        self.assertEqual(active_cosmetic_id(nonfighter, 5), 0)
        self.assertFalse(has_active_cosmetic(nonfighter, 5, 1234))

    def test_missing_or_malformed_actor_components_remain_unknown(self):
        for state, category in (
            (NativeCosmeticState(None, None, None), 5),
            (NativeCosmeticState(True, None, {}), 5),
            (NativeCosmeticState(True, {5: None}, {}), 5),
            (NativeCosmeticState(True, {3: 0}, None), 9),
        ):
            with self.subTest(state=state), self.assertRaises(ValueError):
                active_cosmetic_id(state, category)
        with self.assertRaises(ValueError):
            has_active_cosmetic(NativeCosmeticState(True, {}, None), 5, 99)

    def test_criteria_validate_signatures_and_preserve_java_int_cast(self):
        state = NativeCosmeticState(True, {3: -1, 4: 0, 5: (), 6: 0, 7: 0}, {})
        context = ConditionContext(
            {},
            active_cosmetic_id_query=lambda category: active_cosmetic_id(
                state, category
            ),
            has_active_cosmetic_query=lambda category, identity: has_active_cosmetic(
                state, category, identity
            ),
        )
        self.assertTrue(evaluate_condition("GetActiveCosmeticId(3) == -1", context))
        self.assertFalse(evaluate_condition("HasActiveCosmeticId(9, 42)", context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetActiveCosmeticId() == 0", context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition("HasActiveCosmeticId(9)", context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetActiveCosmeticId(3) == 0", ConditionContext({}))


if __name__ == "__main__":
    unittest.main()
