import unittest
from unittest.mock import patch

from wakfu_server.combat_actor_snapshot import ActorSnapshot, initialize_fight_snapshots
from wakfu_server.combat_state import Actor, Fight


class NativeQISnapshotAtomicityTests(unittest.TestCase):
    def test_invalid_prepared_radius_rejects_before_any_actor_installation(self):
        first = Actor(1, 0, (0, 0, 0), 20, 6, 3, 10, 10)
        second = Actor(2, 1, (1, 0, 0), 30, 6, 3, 11, 10)
        fight = Fight(
            99,
            [first, second],
            {first.position, second.position},
            {0: {first.position}, 1: {second.position}},
        )
        fight.native_qi_snapshot = dict(x=0, y=0, width=2, height=1, cell_masks=[0, 0])
        pending_order = fight.native_qi_fresh_actor_order
        original_ids = (first.native_obstacle_id, second.native_obstacle_id)

        def prepared_snapshot(character, actor, **kwargs):
            return ActorSnapshot(
                actor_id=actor.id,
                stats={1: actor.hp, 2: actor.ap, 3: actor.mp, 35: actor.initiative},
                minima={1: 0, 2: 0, 3: 0},
                maxima={1: actor.max_hp, 2: actor.max_ap, 3: actor.max_mp},
                frozen=frozenset(),
                physical_radius=0 if actor is first else 128,
                provenance="direct prepared-snapshot boundary fixture",
                native_los_height=0,
            )

        with patch(
            "wakfu_server.combat_actor_snapshot.build_player_snapshot",
            side_effect=prepared_snapshot,
        ), patch.object(ActorSnapshot, "install", autospec=True) as install:
            with self.assertRaisesRegex(ValueError, "registration facts"):
                initialize_fight_snapshots(
                    fight,
                    characters={1: {}, 2: {}},
                    monsters={},
                    wp_resources={1: (6, 6), 2: (6, 6)},
                    running_effects={1: (), 2: ()},
                    initial_effect_uid=41,
                )

        install.assert_not_called()
        self.assertIsNone(first.effect_stats)
        self.assertIsNone(second.effect_stats)
        self.assertIsNone(first.physical_radius)
        self.assertIsNone(second.physical_radius)
        self.assertEqual(
            (first.native_obstacle_id, second.native_obstacle_id), original_ids
        )
        self.assertIsNone(fight.native_qi_slots)
        self.assertEqual(fight.native_qi_fresh_actor_order, pending_order)
        self.assertIsNone(fight.native_effect_uid_next)

    def test_outside_arena_actor_rejects_before_any_snapshot_or_uid_install(self):
        first = Actor(1, 0, (0, 0, 0), 20, 6, 3, 10, 10)
        outside = Actor(2, 1, (2, 0, 0), 30, 6, 3, 11, 10)
        fight = Fight(
            99,
            [first, outside],
            {first.position, outside.position},
            {0: {first.position}, 1: {outside.position}},
        )
        fight.native_qi_snapshot = dict(x=0, y=0, width=2, height=1, cell_masks=[0, 0])
        pending_order = fight.native_qi_fresh_actor_order
        original_ids = (first.native_obstacle_id, outside.native_obstacle_id)

        def prepared_snapshot(character, actor, **kwargs):
            return ActorSnapshot(
                actor_id=actor.id,
                stats={1: actor.hp, 2: actor.ap, 3: actor.mp, 35: actor.initiative},
                minima={1: 0, 2: 0, 3: 0},
                maxima={1: actor.max_hp, 2: actor.max_ap, 3: actor.max_mp},
                frozen=frozenset(),
                physical_radius=0,
                provenance="direct fresh snapshot boundary fixture",
                native_los_height=0,
            )

        with patch(
            "wakfu_server.combat_actor_snapshot.build_player_snapshot",
            side_effect=prepared_snapshot,
        ), patch.object(ActorSnapshot, "install", autospec=True) as install:
            with self.assertRaisesRegex(ValueError, "outside serialized arena"):
                initialize_fight_snapshots(
                    fight,
                    characters={1: {}, 2: {}},
                    monsters={},
                    wp_resources={1: (6, 6), 2: (6, 6)},
                    running_effects={1: (), 2: ()},
                    initial_effect_uid=41,
                )

        install.assert_not_called()
        self.assertIsNone(first.effect_stats)
        self.assertIsNone(outside.effect_stats)
        self.assertIsNone(first.physical_radius)
        self.assertIsNone(outside.physical_radius)
        self.assertEqual(
            (first.native_obstacle_id, outside.native_obstacle_id), original_ids
        )
        self.assertIsNone(fight.native_qi_slots)
        self.assertEqual(fight.native_qi_fresh_actor_order, pending_order)
        self.assertIsNone(fight.native_effect_uid_next)


if __name__ == "__main__":
    unittest.main()
