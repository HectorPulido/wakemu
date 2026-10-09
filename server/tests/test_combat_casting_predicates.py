import json
from pathlib import Path
import unittest

from wakfu_server.combat_conditions import (
    ConditionContext,
    evaluate_condition,
    UnknownCondition,
)
from wakfu_server.combat_free_cell_condition import (
    native_cell_direction,
    native_free_cell,
)
from wakfu_server.combat_gate_conditions import native_gate_count
from wakfu_server.combat_area_predicates import is_own_area
from types import SimpleNamespace


class NativeCastingPredicateTests(unittest.TestCase):
    def test_owned_area_accepts_all_types_and_true_selects_only_center(self):
        row = dict(
            uid=101,
            owner_id=7,
            native_type_id=19,
            reference=823,
            native_area_contract="faZ",
            cell=(2, 3, 0),
            native_cells_xy=((2, 3), (3, 3)),
        )
        fight = SimpleNamespace(native_effect_areas={101: row})
        kwargs = dict(
            source_id=7, target_kind="cell", pv_owner_query=lambda value: value
        )
        self.assertTrue(
            is_own_area(fight, cell=(2, 3, 99), exclude_center=True, **kwargs)
        )
        self.assertFalse(
            is_own_area(fight, cell=(3, 3, 0), exclude_center=True, **kwargs)
        )
        self.assertTrue(is_own_area(fight, cell=(3, 3, 0), **kwargs))
        self.assertFalse(
            is_own_area(
                fight,
                source_id=8,
                target_kind="area",
                target_id=101,
                pv_owner_query=lambda value: value,
            )
        )

    def test_original_direction_oracle(self):
        path = (
            Path(__file__).resolve().parents[2]
            / "server/test-fixtures/combat/casting-predicates.json"
        )
        for row in json.loads(path.read_text())["direction_rows"]:
            expected = None if row["vector"] is None else tuple(row["vector"])
            self.assertEqual(
                native_cell_direction((0, 0), (row["x"], row["y"])), expected
            )

    def test_rotated_point_checks_terrain_center_blocker_and_any_obstacle(self):
        checked = []

        def terrain(x, y):
            checked.append((x, y))
            return True

        options = dict(
            terrain_free=terrain, area_blockers=(), first_obstacle=lambda x, y: False
        )
        self.assertTrue(native_free_cell((4, 4, 0), (4, 8, 0), 2, 1, **options))
        self.assertEqual(checked, [(3, 6)])
        options["area_blockers"] = (((3, 6, 99), True),)
        self.assertFalse(native_free_cell((4, 4, 0), (4, 8, 0), 2, 1, **options))
        options["area_blockers"] = (((3, 6, 99), False),)
        options["first_obstacle"] = lambda x, y: True
        self.assertFalse(native_free_cell((4, 4, 0), (4, 8, 0), 2, 1, **options))
        self.assertFalse(native_free_cell((4, 4, 0), (4, 4, 0), 0, 0, **options))

    def test_gate_owner_and_team_are_distinct_and_type_filtered(self):
        rows = [
            dict(native_type_id=19, owner_id=7, native_fight_affiliation=2),
            dict(native_type_id=19, owner_id=8, native_fight_affiliation=2),
            dict(native_type_id=12, owner_id=7, native_fight_affiliation=2),
        ]
        self.assertEqual(
            native_gate_count(rows, actor_id=7, affiliation=2, mode="forOwner"), 1
        )
        self.assertEqual(
            native_gate_count(rows, actor_id=7, affiliation=2, mode="forTeam"), 2
        )
        self.assertEqual(
            native_gate_count(rows, actor_id=None, affiliation=None, mode="forTeam"), 0
        )
        self.assertEqual(
            native_gate_count(rows, actor_id=7, affiliation=2, mode="other"), 0
        )

    def test_shared_evaluator_routes_and_missing_authority(self):
        seen = []
        context = ConditionContext(
            {},
            free_cell_query=lambda *args: seen.append(args) or True,
            gate_count_query=lambda selector, mode: 2,
            area_identity_query=lambda name, value: name == "IsOwnArea" and value,
        )
        self.assertTrue(evaluate_condition('IsFreeCell("target",1,0)', context))
        self.assertEqual(seen, [("target", 1, 0)])
        self.assertTrue(
            evaluate_condition('NbGates("caster","forOwner") == 2', context)
        )
        self.assertTrue(evaluate_condition("IsOwnArea(true)", context))
        with self.assertRaises(UnknownCondition):
            evaluate_condition('IsFreeCell("target",1,0)', ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition('IsFreeCell("target",GetLevel(),0)', context)


if __name__ == "__main__":
    unittest.main()
