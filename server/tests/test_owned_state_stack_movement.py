from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import unittest
from types import SimpleNamespace
from owned_state_stack import (
    native_path,
    approach_native_producer_target,
    restore_native_producer_position,
)


class MovementTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch

        patcher = patch(
            "owned_state_stack.native_segment_cost",
            side_effect=lambda fight, caster, path: (0, len(path)),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def fixture(self):
        actors = {
            -200: SimpleNamespace(position=(0, 0, 0), ap=6, mp=6, hp=100, team=1),
            7: SimpleNamespace(position=(4, 0, 0), mp=3, hp=100, team=0),
        }
        return SimpleNamespace(
            actors=actors, walkable={(x, 0, 0) for x in range(5)}, edges=None
        )

    def provider(self, fight):
        class Provider:
            def commit(self, runtime, action, serialize):
                actor = fight.actors[-200]
                actor.mp -= len(action["path"])
                actor.position = tuple(action["path"][-1])
                return [b"actual-packet"]

        return Provider()

    def test_real_movement_approaches_and_restores_without_resource_grant(self):
        fight = self.fixture()
        provider = self.provider(fight)
        proof = approach_native_producer_target(
            fight, -200, 7, [1, 1], provider, lambda f: f, None
        )
        self.assertEqual(fight.actors[-200].position, (3, 0, 0))
        self.assertEqual(fight.actors[-200].mp, 3)
        restore_native_producer_position(
            fight, -200, proof, provider, lambda f: f, None
        )
        self.assertEqual(fight.actors[-200].position, (0, 0, 0))
        self.assertEqual(fight.actors[-200].mp, 0)

    def test_directed_edges_and_occupied_cells_are_not_bypassed(self):
        fight = self.fixture()
        fight.edges = {((0, 0, 0), (1, 0, 0))}
        with self.assertRaises(ValueError):
            native_path(fight, -200, lambda cell: cell == (3, 0, 0))
        fight.edges = None
        fight.actors[9] = SimpleNamespace(position=(2, 0, 0), hp=100, team=0)
        with self.assertRaises(ValueError):
            native_path(fight, -200, lambda cell: cell == (3, 0, 0))

    def test_wrong_team_or_no_commit_rejected(self):
        fight = self.fixture()
        fight.actors[7].team = 1
        with self.assertRaises(ValueError):
            approach_native_producer_target(
                fight, -200, 7, [1, 1], self.provider(fight), lambda f: f, None
            )
        fight = self.fixture()
        bad = SimpleNamespace(commit=lambda *args: [])
        with self.assertRaises(ValueError):
            approach_native_producer_target(
                fight, -200, 7, [1, 1], bad, lambda f: f, None
            )

    def test_native_tackle_cost_splits_path_and_uses_only_normal_turn_refill(self):
        from unittest.mock import patch
        from owned_state_stack import commit_native_path

        fight = self.fixture()
        actor = fight.actors[-200]
        actor.ap = 4
        actor.mp = 5
        refills = []

        def end_turn(actual):
            refills.append((actor.ap, actor.mp))
            actor.ap = 4
            actor.mp = 5

        def cost(actual, caster, path):
            return 4, len(path) + 4

        class Provider:
            def commit(self, runtime, action, serialize):
                actor.ap -= 4
                actor.mp -= len(action["path"]) + 4
                actor.position = tuple(action["path"][-1])
                return [b"normal-move"]

        with patch("owned_state_stack.native_segment_cost", side_effect=cost), patch(
            "monster_spell_scenarios.finish_current_turn", side_effect=end_turn
        ), patch("monster_spell_scenarios.advance_to"):
            proof = commit_native_path(
                fight,
                -200,
                [(1, 0, 0), (2, 0, 0), (3, 0, 0)],
                Provider(),
                lambda f: f,
                None,
            )
        self.assertEqual(len(proof["segments"]), 3)
        self.assertEqual(proof["normal_turns"], 2)
        self.assertEqual(len(refills), 2)
        self.assertEqual(actor.position, (3, 0, 0))
        self.assertEqual((actor.ap, actor.mp), (0, 0))

    def test_last_approach_zero_ap_requires_normal_turn_before_producer(self):
        from unittest.mock import patch
        from owned_state_stack import ensure_native_producer_resources

        fight = self.fixture()
        actor = fight.actors[-200]
        actor.ap = 0
        actor.mp = 0
        actor.effect_stats = {4: 0}

        def normal_end(actual):
            actor.ap = 4
            actor.mp = 5

        with patch(
            "monster_spell_scenarios.finish_current_turn", side_effect=normal_end
        ) as end, patch("monster_spell_scenarios.advance_to"):
            proof = ensure_native_producer_resources(fight, -200, [1, 0, 0])
        self.assertEqual(end.call_count, 1)
        self.assertEqual((actor.ap, actor.mp, actor.effect_stats[4]), (4, 5, 0))
        self.assertTrue(proof["normal_turn_advanced"])
        with self.assertRaises(ValueError):
            ensure_native_producer_resources(fight, -200, [1, 0, 1])

    def test_initial_player_spare_preserves_native_consumer_los_corridor(self):
        from owned_state_stack import producer_spare_eligible

        recipe = {"native_producer_target_id": -201}
        source = (-8, -7, -1)
        target = (-12, -7, -1)
        self.assertFalse(producer_spare_eligible(recipe, source, target, (-9, -7, -1)))
        self.assertFalse(producer_spare_eligible(recipe, source, target, (-10, -7, -1)))
        self.assertTrue(producer_spare_eligible(recipe, source, target, (-9, -8, -1)))
        self.assertFalse(producer_spare_eligible(recipe, source, target, (-9, -8, 0)))
        self.assertTrue(producer_spare_eligible({}, source, target, (-9, -7, -1)))


if __name__ == "__main__":
    unittest.main()
