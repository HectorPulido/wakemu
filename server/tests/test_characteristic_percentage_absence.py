"""Affected eJz semantics: proven absent PC differs from unknown metadata."""
import unittest
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class NativePercentageAbsenceTests(unittest.TestCase):
    def test_source_proven_area_without_hp_returns_native_minus_one(self):
        area = ConditionActor(
            actor_id=9001,
            is_native_ehg=True,
            is_native_fighter=False,
            characteristics={},
            characteristic_maxima={},
            total_hp_absent_characteristics=frozenset({"HP", "VIRTUAL_HP"}),
        )
        context = ConditionContext({"target": area})
        for name in ("GetCharacInPct", "GetCharacPct", "GetCharacteristicPct"):
            with self.subTest(name=name):
                self.assertTrue(
                    evaluate_condition(f'{name}("hp","target")==-1', context)
                )
                self.assertTrue(
                    evaluate_condition(f'{name}("hp","target")<=70', context)
                )
        self.assertEqual(area.characteristics, {})
        self.assertEqual(area.characteristic_maxima, {})

    def test_missing_or_conflicting_characteristic_authority_still_rejects(self):
        for actor in (
            ConditionActor(characteristics={}, characteristic_maxima={}),
            ConditionActor(
                characteristics={},
                characteristic_maxima={},
                total_hp_absent_characteristics={"HP"},
            ),
            ConditionActor(
                characteristics={},
                characteristic_maxima={"HP": 100},
                total_hp_absent_characteristics=frozenset({"HP"}),
            ),
            ConditionActor(
                characteristics={"HP": 30},
                characteristic_maxima={"HP": 100},
                total_hp_absent_characteristics=frozenset({"HP"}),
            ),
        ):
            with self.subTest(actor=actor):
                with self.assertRaises(UnknownCondition):
                    evaluate_condition(
                        'GetCharacInPct("hp","target")<=70',
                        ConditionContext({"target": actor}),
                    )

    def test_percentage_absence_does_not_invent_raw_or_maximum_hp(self):
        actor = ConditionActor(
            characteristics={},
            characteristic_maxima={},
            total_hp_absent_characteristics=frozenset({"HP"}),
        )
        for name in (
            "GetCharac",
            "GetCharacteristic",
            "GetCharacMax",
            "GetCharacteristicMax",
        ):
            with self.subTest(name=name):
                with self.assertRaises(UnknownCondition):
                    evaluate_condition(
                        f'{name}("hp","target")==0', ConditionContext({"target": actor})
                    )

    def test_actual_hp_area_and_fighter_still_use_native_percentage(self):
        for fighter in (False, True):
            actor = ConditionActor(
                is_native_fighter=fighter,
                characteristics={"HP": 71},
                characteristic_maxima={"HP": 100},
                total_hp_absent_characteristics=frozenset({"VIRTUAL_HP"}),
            )
            context = ConditionContext({"target": actor})
            self.assertFalse(
                evaluate_condition('GetCharacInPct("hp","target")<=70', context)
            )


if __name__ == "__main__":
    unittest.main()
