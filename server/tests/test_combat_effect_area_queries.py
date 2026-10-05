import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_area_queries import (
    specific_area_count,
    cell_contains_type,
)


class NativeAreaQueriesTests(unittest.TestCase):
    def fixture(self):
        return SimpleNamespace(
            native_effect_areas={
                901: dict(
                    uid=901,
                    reference=1546,
                    cell=(2, -3, 4),
                    owner_id=7,
                    native_hour_contract=True,
                )
            }
        )

    def test_eLn_uses_reference_not_uid_and_ignores_height(self):
        f = self.fixture()
        query = lambda ref, lo, hi: specific_area_count(
            f,
            source_id=7,
            center=(2, -2, 99),
            area_reference=ref,
            minimum=lo,
            maximum=hi,
            owned=True,
        )
        self.assertEqual(query(1546, 1, 1), 1)
        self.assertEqual(query(901, 1, 1), 0)
        self.assertEqual(query(1546, 99, -1), 1)
        self.assertEqual(query(1546, 2, 3), 0)
        self.assertEqual(
            specific_area_count(
                f,
                source_id=8,
                center=(2, -2, 0),
                area_reference=1546,
                minimum=0,
                maximum=2,
                owned=True,
            ),
            0,
        )

    def test_eID_point_shape_xy_and_native_hour_type(self):
        f = self.fixture()
        self.assertTrue(
            cell_contains_type(
                f, cell=(2, -3, 100), area_type=1, source_id=7, owned=True
            )
        )
        self.assertFalse(cell_contains_type(f, cell=(2, -3, 4), area_type=0))
        self.assertFalse(
            cell_contains_type(f, cell=(2, -3, 4), area_type=1, source_id=8, owned=True)
        )
        self.assertFalse(cell_contains_type(f, cell=(2, -2, 4), area_type=1))

    def test_common_condition_queries_and_missing_authority(self):
        from wakfu_server.combat_conditions import (
            ConditionContext,
            evaluate_condition,
            UnknownCondition,
        )

        f = self.fixture()
        context = ConditionContext(
            {},
            specific_area_range_query=lambda selector, ref, lo, hi, owned: specific_area_count(
                f,
                source_id=7,
                center=(2, -2, 100),
                area_reference=ref,
                minimum=lo,
                maximum=hi,
                owned=owned,
            ),
            cell_area_type_query=lambda kind, owned: cell_contains_type(
                f, cell=(2, -3, 100), area_type=kind, source_id=7, owned=owned
            ),
        )
        self.assertTrue(
            evaluate_condition(
                'GetSpecificEffectAreaCountInRange("caster",1546,1,1,True) == 1',
                context,
            )
        )
        self.assertTrue(
            evaluate_condition("CellContainsEffectAreaType(1,True)", context)
        )
        self.assertFalse(evaluate_condition("CellContainsEffectAreaType(0)", context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition("CellContainsEffectAreaType(1)", ConditionContext({}))

    def test_eOF_uses_area_reference_and_parent_pv_owner(self):
        from wakfu_server.combat_effect_area_queries import own_specific_area
        from wakfu_server.combat_conditions import ConditionContext, evaluate_condition

        f = self.fixture()
        query = lambda ref, sel: own_specific_area(
            f, reference=ref, selector=sel, caster_id=7, target_id=901, cell=(2, -3, 4)
        )
        self.assertTrue(
            evaluate_condition(
                "IsOwnSpecificArea(1546)",
                ConditionContext({}, own_specific_area_query=query),
            )
        )
        self.assertFalse(query(901, "target"))
        self.assertFalse(query(1546, "caster"))
        self.assertFalse(
            own_specific_area(
                f,
                reference=1546,
                selector="target",
                caster_id=8,
                target_id=901,
                cell=(2, -3, 4),
            )
        )

    def test_eIE_specific_reference_owner_and_xy(self):
        from wakfu_server.combat_effect_area_queries import cell_contains_specific
        from wakfu_server.combat_conditions import (
            ConditionContext,
            evaluate_condition,
            UnknownCondition,
        )

        f = self.fixture()
        query = lambda ref, owned: cell_contains_specific(
            f, cell=(2, -3, 99), reference=ref, source_id=7, owned=owned
        )
        context = ConditionContext({}, cell_specific_area_query=query)
        self.assertTrue(
            evaluate_condition("CellContainsSpecificEffectArea(1546,True)", context)
        )
        self.assertFalse(
            evaluate_condition("CellContainsSpecificEffectArea(901)", context)
        )
        self.assertFalse(
            cell_contains_specific(
                f, cell=(2, -3, 99), reference=1546, source_id=8, owned=True
            )
        )
        self.assertTrue(
            cell_contains_specific(
                f, cell=(2, -3, 99), reference=1546, source_id=901, owned=True
            )
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "CellContainsSpecificEffectArea(1546)", ConditionContext({})
            )

    def test_eLw_type_team_center_and_negative_maximum(self):
        from wakfu_server.combat_effect_area_queries import team_area_count
        from wakfu_server.combat_conditions import ConditionContext, evaluate_condition

        f = self.fixture()
        f.actors = {7: SimpleNamespace(team=0), 8: SimpleNamespace(team=1)}
        f.native_effect_areas[902] = dict(
            uid=902,
            reference=1557,
            cell=(2, -2, 0),
            owner_id=8,
            native_hour_contract=True,
        )
        query = lambda selector, kind, lo, hi: team_area_count(
            f, source_id=7, center=(2, -2, 99), area_type=kind, minimum=lo, maximum=hi
        )
        context = ConditionContext({}, team_area_range_query=query)
        self.assertTrue(
            evaluate_condition(
                'GetTeamEffectAreaCountInRange("target",1,1,1) == 1', context
            )
        )
        self.assertEqual(query("caster", 1, 99, -1), 1)
        self.assertEqual(query("caster", 1546, 0, 5), 0)
        self.assertEqual(
            team_area_count(
                f, source_id=901, center=(2, -3, 0), area_type=1, minimum=0, maximum=-1
            ),
            0,
        )
