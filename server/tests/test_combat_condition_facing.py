from types import SimpleNamespace
import unittest

from wakfu_server.combat_condition_facing import native_backstabbed, native_facestabbed
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_ordinary_authority import native_facing


class NativeFacingConditionTests(unittest.TestCase):
    def setUp(self):
        self.caster = SimpleNamespace(position=(0, 0, 0), direction=1)
        self.target = SimpleNamespace(position=(-1, 0, 0), direction=5)
        self.fight = SimpleNamespace(
            actors={7: self.caster, -7: self.target}, native_effect_areas={}
        )
        self.metadata = ConditionActor(
            is_native_fighter=True, fight_properties=frozenset()
        )

    def query(self, selector):
        selected, opposite = (-7, 7) if selector == "target" else (7, -7)
        return native_backstabbed(self.fight, selected, opposite, self.metadata)

    def test_native_selectors_live_rotation_and_live_position(self):
        context = ConditionContext({}, backstabbed_query=self.query)
        for expression in (
            "IsBackstabbed()",
            'IsBackstabbed("anything")',
            'IsBackstabbed("TARGET")',
        ):
            self.assertTrue(evaluate_condition(expression, context), expression)
        self.caster.direction = 5
        self.assertFalse(evaluate_condition("IsBackstabbed()", context))
        self.target.position = (1, 0, 0)
        self.assertTrue(evaluate_condition("IsBackstabbed()", context))

    def test_front_predicate_shares_native_selector_and_locator_guards(self):
        def front(selector):
            selected, opposite = (-7, 7) if selector == "target" else (7, -7)
            return native_facestabbed(self.fight, selected, opposite, self.metadata)

        context = ConditionContext({}, facestabbed_query=front)
        self.caster.direction = 5
        self.target.direction = 1
        for expression in (
            "IsFacestabbed()",
            'IsFacestabbed("anything")',
            'IsFacestabbed("TARGET")',
        ):
            self.assertTrue(evaluate_condition(expression, context))
        self.target.position = (0, 1, 0)
        self.assertFalse(evaluate_condition("IsFacestabbed()", context))
        self.assertFalse(native_facestabbed(self.fight, 7, None, self.metadata))
        hidden = ConditionActor(
            is_native_fighter=True, fight_properties=frozenset({47})
        )
        self.assertFalse(native_facestabbed(self.fight, 7, -7, hidden))
        for expression in (
            "True or IsFacestabbed(1)",
            'False and IsFacestabbed("target", "caster")',
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, context)

    def test_explicit_cell_not_pv_but_registered_area_is_pv(self):
        self.assertFalse(native_backstabbed(self.fight, 7, None, self.metadata))
        self.fight.native_effect_areas[101] = {"cell": (-1, 0, 0)}
        self.assertTrue(native_backstabbed(self.fight, 7, 101, self.metadata))
        self.assertFalse(native_backstabbed(self.fight, 101, 7, None))

    def test_null_locator_property47_and_nonfighter_are_false(self):
        self.caster.direction = None
        hidden = ConditionActor(
            is_native_fighter=True, fight_properties=frozenset({47})
        )
        self.assertFalse(native_backstabbed(self.fight, 7, -7, hidden))
        nonfighter = ConditionActor(is_native_fighter=False)
        self.assertFalse(native_backstabbed(self.fight, 7, -7, nonfighter))
        self.assertFalse(native_backstabbed(self.fight, None, -7, None))

    def test_unknown_direction_and_missing_authority_remain_unknown(self):
        self.caster.direction = None
        with self.assertRaisesRegex(UnknownCondition, "direction"):
            evaluate_condition(
                "IsBackstabbed()", ConditionContext({}, backstabbed_query=self.query)
            )
        for metadata in (None, ConditionActor(is_native_fighter=True)):
            with self.assertRaises(ValueError):
                native_backstabbed(self.fight, 7, -7, metadata)
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsBackstabbed()", ConditionContext({}))

    def test_native_signature_rejects_invalid_short_circuited_branches(self):
        for expression in (
            "True or IsBackstabbed(1)",
            'False and IsBackstabbed("target", "caster")',
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    expression, ConditionContext({}, backstabbed_query=self.query)
                )

    def test_same_xyz_front_vertical_only_side_and_java_subtraction_overflow(self):
        self.target.position = self.caster.position
        self.assertEqual(native_facing(self.target, self.caster), "FRONT")
        self.target.position = (0, 0, 1)
        self.assertEqual(native_facing(self.target, self.caster), "SIDE")
        self.caster.position = (-2147483648, 0, 0)
        self.target.position = (2147483647, 0, 0)
        self.assertEqual(native_facing(self.target, self.caster), "BACK")


if __name__ == "__main__":
    unittest.main()
