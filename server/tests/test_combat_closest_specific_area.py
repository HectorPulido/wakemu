import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_area_queries import closest_specific_area_distance
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class ClosestSpecificAreaTests(unittest.TestCase):
    def fight(self):
        def row(uid, x, owner, reference=55):
            return dict(
                uid=uid,
                owner_id=owner,
                reference=reference,
                native_area_contract="faY",
                cell=(x, 0, 0),
            )

        return SimpleNamespace(
            actors={7: SimpleNamespace(position=(0, 0, 0))},
            native_effect_areas={
                1: row(1, 0, 7),
                2: row(2, 3, 7),
                3: row(3, 1, 8),
                4: row(4, 1, 7, 99),
            },
        )

    def query(self, **kwargs):
        args = dict(selected_id=7, reference=55, use_path=False)
        args.update(kwargs)
        return closest_specific_area_distance(self.fight(), **args)

    def test_closest_positive_distance_filters_reference_and_direct_owner(self):
        self.assertEqual(self.query(), 1)
        self.assertEqual(self.query(owner_id=7), 3)
        self.assertEqual(self.query(owner_id=99), -1)

    def test_null_selected_and_nonfighter_area_return_negative_one(self):
        self.assertEqual(self.query(selected_id=None), -1)
        self.assertEqual(self.query(selected_id=1), -1)
        with self.assertRaises(ValueError):
            self.query(selected_id=777)

    def test_path_mode_requires_actual_native_path_result(self):
        with self.assertRaises(ValueError):
            self.query(use_path=True)
        self.assertEqual(
            self.query(use_path=True, path_distance=lambda actor, row: -1), -1
        )
        self.assertEqual(
            self.query(
                use_path=True, path_distance=lambda actor, row: row["cell"][0] + 2
            ),
            2,
        )

    def test_empty_prototype_returns_negative_one_even_in_path_mode(self):
        self.assertEqual(self.query(reference=999, use_path=True), -1)

    def test_numeric_condition_uses_callback_without_rewriting_negative_one(self):
        seen = []

        def query(*args):
            seen.append(args)
            return -1

        context = ConditionContext({}, closest_specific_area_query=query)
        self.assertTrue(
            evaluate_condition(
                'GetDistanceToClosestSpecificArea("target",55,False,"caster") <= 6',
                context,
            )
        )
        self.assertEqual(seen, [("target", 55, False, "caster")])

    def test_missing_callback_and_malformed_signature_reject(self):
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'GetDistanceToClosestSpecificArea("target",55,False) <= 6',
                ConditionContext({}),
            )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'GetDistanceToClosestSpecificArea("target",55) <= 6',
                ConditionContext({}),
            )
