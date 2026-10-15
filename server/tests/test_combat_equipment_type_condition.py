"""Native eMm predicate operands, ancestry and missing authority boundaries."""
import unittest
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat.combat_equipment_type_condition import matches_types


class EquipmentTypeConditionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {
            "items": {"12": 223, "2022": 103},
            "types": {
                "223": 519,
                "519": 100,
                "100": 109,
                "109": 0,
                "103": 118,
                "118": 109,
            },
        }

    def test_direct_type_and_all_ancestors_with_java_short_narrowing(self):
        for requested in (223, 519, 100, 109, 65536 + 223):
            self.assertTrue(matches_types([12], [requested], self.catalog))
        self.assertFalse(matches_types([12], [103, 118], self.catalog))
        self.assertTrue(matches_types([12, 2022], [103], self.catalog))

    def test_target_inventory_flags_and_default_caster_are_preserved(self):
        seen = []

        def query(types, target, inventory):
            seen.append((types, target, inventory))
            return matches_types([12] if target else [2022], types, self.catalog)

        context = ConditionContext({}, equipment_type_query=query)
        self.assertFalse(evaluate_condition("HasEquipmentType(100)", context))
        self.assertTrue(
            evaluate_condition('HasEquipmentType(100,"TARGET","inventory")', context)
        )
        self.assertEqual(seen, [((100,), False, False), ((100,), True, True)])
        self.assertTrue(evaluate_condition("HasEquipmentType(1,103)", context))

    def test_unknown_authority_or_slot_never_becomes_false_success(self):
        with self.assertRaises(UnknownCondition):
            evaluate_condition("HasEquipmentType(100)", ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'HasEquipmentType(100,"FIRST_WEAPON")',
                ConditionContext({}),
                validate_only=True,
            )
        with self.assertRaises(ValueError):
            matches_types([999999], [100], self.catalog)
        self.assertFalse(matches_types([], [100], self.catalog))

    def test_all_three_monsters_original_guard_validates(self):
        guard = " or ".join(
            "HasEquipmentType(%d)" % n
            for n in (
                101,
                108,
                110,
                111,
                113,
                114,
                115,
                117,
                189,
                219,
                223,
                253,
                254,
                112,
            )
        )
        self.assertTrue(
            evaluate_condition(guard, ConditionContext({}), validate_only=True)
        )
