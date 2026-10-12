"""Natural monster work must revalidate live map-and-instance membership."""
import unittest
import threading
from unittest.mock import Mock, MagicMock, patch
from contextlib import ExitStack

import test_ecology_mobs_apply as fixtures
from wakfu_server import (
    ecology_mobs,
    monster_maturation,
    monster_reproduction,
    monster_wander,
)
from wakfu_server.world import World


class EmptyMapMonsterApplyTests(unittest.TestCase):
    def test_prepared_natural_work_cannot_commit_after_last_player_leaves(self):
        # Includes outbox publication: an empty map must not receive a delayed
        # spawn merely because the worker planned it before the departure.
        for kind in (
            "wander",
            "maturation",
            "reproduction",
            "publish_maturation",
            "publish_reproduction",
        ):
            for players in (
                [],
                [
                    dict(
                        id=1,
                        map_id=1134,
                        instance_id=0,
                        x=20,
                        y=20,
                        z=0,
                        _ecology_active=False,
                    )
                ],
                [dict(id=1, map_id=1134, instance_id=99, x=20, y=20, z=0)],
                [dict(id=1, map_id=1135, instance_id=0, x=20, y=20, z=0)],
            ):
                with self.subTest(kind=kind, players=players):
                    helper = fixtures.EcologyMobsApplyTests()
                    proposal = dict(helper.proposal(), kind=kind)
                    groups = fixtures.FakeGroups()
                    harvests = fixtures.FakeHarvests()
                    world = fixtures.FakeWorld(players)
                    with patch.object(
                        monster_wander, "policy", return_value=helper.configuration
                    ), patch.object(
                        monster_maturation, "policy", return_value=helper.configuration
                    ), patch.object(
                        monster_reproduction,
                        "policy",
                        return_value=helper.configuration,
                    ), patch.object(
                        ecology_mobs, "_edges", return_value={}
                    ), patch.object(
                        monster_maturation, "attempt"
                    ) as mature, patch.object(
                        monster_reproduction, "attempt"
                    ) as reproduce:
                        result = ecology_mobs.apply(
                            Mock(),
                            groups,
                            harvests,
                            world,
                            proposal,
                            world_epoch="boot-a",
                        )
                    self.assertEqual(result, {"status": "absent"})
                    mature.assert_not_called()
                    reproduce.assert_not_called()
                    self.assertEqual(groups.move_calls, [])
                    self.assertEqual(world.emitted, [])

    def test_empty_snapshot_pauses_both_clocks_without_planning_natural_work(self):
        snapshot = dict(
            world_epoch="boot-a",
            players=[],
            locations=[[1134, 0]],
            previous_locations=[[1134, 0]],
            excluded_ids=[],
            now_ms=500000,
        )
        with patch(
            "wakfu_server.monster_population_cleanup.prepare", return_value=[]
        ), patch.object(monster_wander, "policy", return_value={}), patch.object(
            monster_maturation, "policy", return_value={}
        ), patch.object(
            monster_reproduction, "policy", return_value={}
        ), patch.object(
            monster_maturation, "observe", return_value=[]
        ) as mature, patch.object(
            monster_reproduction, "observe", return_value=[]
        ) as reproduce:
            store = Mock()
            self.assertEqual(ecology_mobs.prepare(store, snapshot), [])
        store.connection.assert_not_called()
        for domain in (mature, reproduce):
            domain.assert_called_once_with(
                store, 1134, 0, present=False, generation="boot-a", now_ms=500000
            )

    def test_worker_clock_generation_tracks_occupancy_episode(self):
        store = MagicMock()
        store.connection.return_value.__enter__.return_value.execute.return_value = []
        snapshot = dict(
            world_epoch="boot-a",
            players=[],
            locations=[[1134, 0]],
            previous_locations=[],
            excluded_ids=[],
            now_ms=1000,
            allow_wander=False,
        )
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "wakfu_server.monster_population_cleanup.prepare", return_value=[]
                )
            )
            stack.enter_context(
                patch("wakfu_server.monster_life_plans.attach", return_value=[])
            )
            stack.enter_context(
                patch.object(
                    monster_reproduction, "dungeon_population", return_value=False
                )
            )
            observations = []
            for domain in (monster_maturation, monster_reproduction):
                stack.enter_context(patch.object(domain, "policy", return_value={}))
                stack.enter_context(
                    patch.object(domain, "unpublished", return_value=[])
                )
                stack.enter_context(patch.object(domain, "pending", return_value=[]))
                observations.append(
                    stack.enter_context(
                        patch.object(domain, "observe", return_value=[])
                    )
                )
            stack.enter_context(patch.object(monster_wander, "policy", return_value={}))
            for episode in (1, 2):
                snapshot["players"] = [
                    dict(id=1, map_id=1134, instance_id=0, presence_generation=episode)
                ]
                self.assertEqual(ecology_mobs.prepare(store, snapshot), [])
            for observe in observations:
                self.assertEqual(
                    [call.kwargs["generation"] for call in observe.call_args_list],
                    ["boot-a:presence:1", "boot-a:presence:2"],
                )

    def test_departure_cannot_interleave_between_presence_check_and_movement_commit(
        self,
    ):
        helper = fixtures.EcologyMobsApplyTests()
        proposal = helper.proposal()
        groups = fixtures.FakeGroups(
            [
                dict(
                    group_id=17,
                    status="available",
                    members=proposal["expected_members"],
                )
            ]
        )
        world = World(lambda _: b"", lambda _: b"", lambda *_: None)
        world.join(
            "lease",
            object(),
            dict(id=1, account_id=1, map_id=1134, instance_id=0, x=20, y=20, z=0),
        )
        departed = threading.Event()
        started = threading.Event()
        threads = []

        def leave():
            started.set()
            world.deactivate_ecology(1, "lease")
            departed.set()

        def move(*args):
            worker = threading.Thread(target=leave)
            threads.append(worker)
            worker.start()
            self.assertTrue(started.wait(1))
            self.assertFalse(
                departed.wait(0.02), "departure escaped the mutation occupancy fence"
            )
            return True

        groups.move_members = move
        with patch.object(
            monster_wander, "policy", return_value=helper.configuration
        ), patch(
            "wakfu_server.ecology_mobs.habitat_destination_allowed", return_value=True
        ):
            result = ecology_mobs.apply(
                Mock(),
                groups,
                fixtures.FakeHarvests(),
                world,
                proposal,
                world_epoch="boot-a",
            )
        for worker in threads:
            worker.join(1)
        self.assertEqual(result, {"status": "applied"})
        self.assertTrue(departed.is_set())
        self.assertEqual(world.ecology_snapshot(), [])
