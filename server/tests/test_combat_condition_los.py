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

    def test_uses_actor_target_native_height_coordinates_and_complete_blockers(self):
        source = SimpleNamespace(id=7, hp=30, position=(2, 3, 4), physical_radius=0)
        target = SimpleNamespace(id=8, hp=30, position=(5, 6, -2), physical_radius=0)
        fight = SimpleNamespace(actors={7: source, 8: target})

        def authority(f, a):
            return SimpleNamespace(native_instance_id=527)

        with patch(
            "wakfu_server.combat_los.authoritative_visible", return_value=False
        ) as visible:
            self.assertFalse(native_condition_los(fight, authority, 7, 8, (99, 99, 99)))
            visible.assert_called_once_with(
                527,
                (2, 3, 4),
                (5, 6, -2),
                fight,
                blocking_footprints={7: {(2, 3)}, 8: {(5, 6)}},
            )
        self.assertFalse(native_condition_los(fight, authority, 100, 8, (1, 2, 3)))


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
