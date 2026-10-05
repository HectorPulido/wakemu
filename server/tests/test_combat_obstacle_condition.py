import unittest
from types import SimpleNamespace
from wakfu_server.combat_obstacle_condition import (
    is_obstacle,
    blocking_flags,
    footprint,
)
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class ObstacleConditionTests(unittest.TestCase):
    def fixture(self):
        actors = {
            7: SimpleNamespace(
                id=7, team=0, physical_radius=0, position=(0, 0, 0), props=frozenset()
            ),
            8: SimpleNamespace(
                id=8,
                team=1,
                physical_radius=0,
                position=(2, 0, 99),
                props=frozenset({5}),
            ),
        }
        fight = SimpleNamespace(
            actors=actors,
            phase="active",
            native_obstacle_cells=frozenset(),
            walkable=frozenset((x, y, 0) for x in range(-1, 4) for y in range(-1, 2)),
        )

        class Authority:
            def __call__(self, f, a):
                return SimpleNamespace(targeting={"is_eHH": True})

            def properties(self, f, a):
                return a.props

        return fight, Authority()

    def test_viewer_anchor_changes_invisible_blocker_without_global_owner(self):
        fight, authority = self.fixture()
        q = lambda viewer: is_obstacle(
            fight, selected_id=8, viewer_id=viewer, actor_authority=authority
        )
        self.assertFalse(q(7))
        self.assertTrue(q(8))
        fight.actors[8].props = frozenset({5, 6})
        self.assertTrue(q(7))

    def test_native_bounds_and_no_terrain_substitution(self):
        self.assertEqual(
            footprint((0, 0, 9), 1, query=True), ((-1, -1), (-1, 0), (0, -1), (0, 0))
        )
        self.assertEqual(len(footprint((0, 0, 9), 1)), 9)
        fight, authority = self.fixture()
        fight.native_obstacle_cells = None
        with self.assertRaisesRegex(ValueError, "static QK"):
            is_obstacle(fight, selected_id=7, viewer_id=7, actor_authority=authority)
        fight.native_obstacle_cells = frozenset()
        with self.assertRaisesRegex(ValueError, "viewer"):
            is_obstacle(fight, selected_id=7, viewer_id=None, actor_authority=authority)
        self.assertFalse(
            is_obstacle(
                fight, selected_id=None, viewer_id=None, actor_authority=authority
            )
        )

    def test_flags_match_native32_combinations(self):
        for ally in (False, True):
            for bits in range(16):
                properties = frozenset(
                    key for i, key in enumerate((5, 6, 18, 54)) if bits >> i & 1
                )
                visible = 18 not in properties and (
                    6 in properties or 5 not in properties
                )
                self.assertEqual(
                    blocking_flags(properties, viewer_ally=ally),
                    (ally or visible, visible and 54 not in properties),
                )

    def test_condition_contract_and_missing_authority(self):
        seen = []
        context = ConditionContext(
            {}, actor_obstacle_query=lambda name: seen.append(name) or True, viewer_id=7
        )
        self.assertTrue(evaluate_condition("IsObstacle()", context))
        self.assertTrue(evaluate_condition('IsObstacle("TaRgEt")', context))
        self.assertEqual(seen, ["caster", "TaRgEt"])
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsObstacle()", ConditionContext({}))

    def test_hp_is_not_native_obstacle_membership_and_mixed_overlap_rejects(self):
        fight, authority = self.fixture()
        fight.actors[8].props = frozenset()
        fight.actors[8].hp = 0
        self.assertTrue(
            is_obstacle(fight, selected_id=8, viewer_id=7, actor_authority=authority)
        )
        fight.actors[8].props = frozenset({5})
        fight.actors[7].position = (2, 0, 0)
        with self.assertRaisesRegex(ValueError, "overlapping QK"):
            is_obstacle(fight, selected_id=8, viewer_id=7, actor_authority=authority)
