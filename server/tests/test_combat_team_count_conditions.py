import unittest
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_team_count_conditions import (
    allies_membership,
    human_actor_type,
    monsters_count,
)


class TeamCountConditionsTests(unittest.TestCase):
    def test_monster_count_native_type_membership_and_signed_arguments(self):
        rows = [
            (0, True, 0, 5347),
            (1, True, 0, 5347),
            (2, True, 1, 5525),
            (1, False, 0, 5347),
            (5, True, 0, 5347),
        ]
        self.assertEqual(monsters_count(rows), 2)
        self.assertEqual(monsters_count(rows, 256, 65536 + 5347), 1)
        self.assertEqual(monsters_count(rows, 255, 65535), 2)
        context = ConditionContext(
            {}, monsters_count_query=lambda *args: monsters_count(rows, *args)
        )
        self.assertTrue(evaluate_condition("GetMonstersInFight(0,5347)==1", context))
        self.assertTrue(evaluate_condition("GetMonstersInFight()==2", context))
        with self.assertRaises(ValueError):
            monsters_count([(None, True, 0, 5347)])

    def test_native_human_type_is_not_control_or_breed(self):
        self.assertEqual(
            [value for value in range(-128, 128) if human_actor_type(value)], [0, 5]
        )
        for value in (None, True, 128):
            with self.assertRaises(ValueError):
                human_actor_type(value)

    def test_allies_membership_does_not_apply_range_property42_or_barrel_filter(self):
        self.assertTrue(allies_membership(True, 0, 0, frozenset({42})))
        self.assertFalse(allies_membership(True, 0, 0, frozenset({114})))
        self.assertFalse(allies_membership(False, 0, 0, frozenset()))
        self.assertFalse(allies_membership(True, 1, 0, frozenset()))
        with self.assertRaises(ValueError):
            allies_membership(None, 0, 0, frozenset())

    def test_native_numeric_routes_preserve_evaluated_range_arguments(self):
        calls = []
        context = ConditionContext(
            {},
            human_allies_range_query=lambda *args: calls.append(args) or 3,
            allies_count_query=lambda selector: calls.append(selector) or 4,
        )
        self.assertTrue(
            evaluate_condition("GetHumanAlliesCountInRange(-1)==3", context)
        )
        self.assertEqual(calls.pop(), (0, -1, "caster", False, False))
        self.assertTrue(
            evaluate_condition(
                'GetHumanAlliesCountInRange(1,3,"target",True,False)==3', context
            )
        )
        self.assertEqual(calls.pop(), (1, 3, "target", True, False))
        self.assertTrue(evaluate_condition('GetAlliesCount("target")==4', context))
        self.assertEqual(calls.pop(), "target")
        with self.assertRaises(UnknownCondition):
            evaluate_condition("GetHumanAlliesCountInRange(-1)>0", ConditionContext({}))
