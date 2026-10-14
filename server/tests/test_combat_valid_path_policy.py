"""Actual canonical movement witnesses; explicit local policy, not Sn parity."""
import copy
import pickle
import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_valid_path_policy import admitted_route, POLICY
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
    current_registry,
)
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class ValidPathPolicyTests(unittest.TestCase):
    def fixture(self):
        actor = Actor(7, 0, (0, 0, 0), 20, 6, 3, 10, 10, owner_id=1, controlled=True)
        enemy = Actor(-7, 1, (3, 3, 0), 30, 0, 0, 1, 10)
        actor.physical_radius = enemy.physical_radius = 0
        cells = {(x, y, 0) for x in range(4) for y in range(4)}
        edges = {
            (a, b)
            for a in cells
            for b in cells
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        }
        fight = Fight(
            99, [actor, enemy], cells, {0: {actor.position}, 1: {enemy.position}}, edges
        )
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=4, height=4, cell_masks=[0] * 16
        )
        install_fresh_actor_slots(
            fight, prepare_fresh_actor_slots(fight, physical_radii={7: 0, -7: 0})
        )
        return fight, actor

    def test_true_witness_replays_actual_movement_and_does_not_mutate_source(self):
        fight, actor = self.fixture()
        before = pickle.dumps(fight, protocol=5)
        original_actor = fight.actors[actor.id]
        original_slots = fight.native_qi_slots
        route = admitted_route(fight, actor.id, (1, 1, 0), limit=2)
        self.assertEqual(len(route), 2)
        self.assertEqual(pickle.dumps(fight, protocol=5), before)
        self.assertIs(fight.actors[actor.id], original_actor)
        self.assertIs(fight.native_qi_slots, original_slots)
        clone = copy.deepcopy(fight)
        event = clone._move_actor(clone.actors[actor.id], route)
        self.assertEqual(clone.actors[actor.id].position, (1, 1, 0))
        self.assertEqual(clone.actors[actor.id].mp, 1)
        self.assertEqual(tuple(event["path"]), route)
        self.assertEqual(
            tuple(current_registry(clone).slots[actor.native_obstacle_id]["position"]),
            (1, 1),
        )
        self.assertIn("not_native_Sn_equivalence", POLICY)

    def test_unreachable_and_insufficient_real_resources_do_not_grant_path(self):
        fight, actor = self.fixture()
        fight.edges = {
            (start, end) for start, end in fight.edges if start != actor.position
        }
        self.assertIsNone(admitted_route(fight, actor.id, (1, 0, 0), limit=2))
        fight, actor = self.fixture()
        actor.mp = 0
        self.assertIsNone(admitted_route(fight, actor.id, (1, 0, 0), limit=2))
        self.assertEqual(actor.mp, 0)

    def test_actual_registered_obstacle_and_bounded_distance_are_respected(self):
        fight, actor = self.fixture()
        self.assertIsNone(admitted_route(fight, actor.id, (3, 3, 0), limit=2))
        # Move actual enemy/QI identity into the only one-step target.
        from wakfu_server.combat_qi_fight import move_registered_actor

        move_registered_actor(fight, fight.actors[-7], (1, 0, 0))
        self.assertIsNone(admitted_route(fight, actor.id, (1, 0, 0), limit=2))

    def test_unsupported_radius_limits_and_missing_qi_remain_unknown(self):
        fight, actor = self.fixture()
        with self.assertRaises(ValueError):
            admitted_route(fight, actor.id, (1, 0, 0), limit=3)
        actor.physical_radius = 1
        with self.assertRaisesRegex(ValueError, "footprint"):
            admitted_route(fight, actor.id, (1, 0, 0), limit=2)
        actor.physical_radius = 0
        fight.native_qi_slots = None
        with self.assertRaises(ValueError):
            admitted_route(fight, actor.id, (1, 0, 0), limit=2)

    def test_real_condition_constructor_routes_literal_and_preserves_missing_authority(
        self,
    ):
        seen = []
        context = ConditionContext(
            {},
            valid_path_query=lambda options, limit: seen.append((options, limit))
            or True,
        )
        self.assertTrue(evaluate_condition("HasValidPathToTarget(2)", context))
        self.assertEqual(seen, [(None, 2)])
        for expression in (
            "HasValidPathToTarget(True)",
            "HasValidPathToTarget(GetLevel())",
            "HasValidPathToTarget(2, 3)",
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, context)
        with self.assertRaises(UnknownCondition):
            evaluate_condition("HasValidPathToTarget(2)", ConditionContext({}))
