import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_conditions import (
    ConditionContext,
    ConditionActor,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.combat_condition_los import native_condition_los


class ConditionLOSTests(unittest.TestCase):
    def test_native_zero_argument_callback_and_unknown(self):
        for value in (True, False):
            self.assertEqual(
                evaluate_condition(
                    "HasLineOfSight()",
                    ConditionContext({}, line_of_sight_query=lambda: value),
                ),
                value,
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("HasLineOfSight()", ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'HasLineOfSight("caster")',
                ConditionContext({}, line_of_sight_query=lambda: True),
            )

    def test_uses_actor_target_cells_and_forwards_live_native_property_authority(self):
        source = SimpleNamespace(id=7, hp=30, position=(2, 3, 4), physical_radius=0)
        target = SimpleNamespace(id=8, hp=30, position=(5, 6, -2), physical_radius=0)
        fight = SimpleNamespace(actors={7: source, 8: target})

        def authority(f, a):
            return SimpleNamespace(native_instance_id=527)

        def properties(f, a):
            return frozenset()

        with patch(
            "wakfu_server.combat_casting_los.native_casting_los", return_value=False
        ) as ray:
            self.assertFalse(
                native_condition_los(
                    fight,
                    authority,
                    7,
                    8,
                    (99, 99, 99),
                    actor_property_authority=properties,
                )
            )
            ray.assert_called_once_with(fight, properties, 7, (5, 6, -2), target)
        self.assertFalse(
            native_condition_los(
                fight,
                authority,
                100,
                8,
                (1, 2, 3),
                actor_property_authority=properties,
            )
        )

    def test_missing_property_population_is_not_treated_as_clear_sight(self):
        source = SimpleNamespace(id=7, position=(2, 3, 4), physical_radius=0)
        target = SimpleNamespace(id=8, position=(5, 6, -2), physical_radius=0)
        fight = SimpleNamespace(actors={7: source, 8: target})
        authority = lambda _fight, _actor: SimpleNamespace(native_instance_id=527)
        with self.assertRaisesRegex(UnknownCondition, "property authority"):
            native_condition_los(fight, authority, 7, 8, target.position)


class OffPlayConditionTests(unittest.TestCase):
    def test_native_baG_selector_missing_and_unknown(self):
        context = ConditionContext(
            {
                "caster": ConditionActor(is_off_play=False),
                "target": ConditionActor(is_off_play=True),
            }
        )
        self.assertFalse(evaluate_condition("IsOffPlay()", context))
        self.assertTrue(evaluate_condition('IsOffPlay("target")', context))
        self.assertFalse(evaluate_condition("IsOffPlay()", ConditionContext({})))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "IsOffPlay()", ConditionContext({"caster": ConditionActor()})
            )
