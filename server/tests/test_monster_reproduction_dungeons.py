"""Dungeon encounters must never enter ecosystem breeding or birth replay."""

from contextlib import contextmanager
import unittest
from unittest.mock import Mock
from types import SimpleNamespace
import threading

from wakfu_server import ecology_mobs

from wakfu_server import monster_reproduction


class RunRegistry:
    def __init__(self, dungeon_ids=()):
        self.dungeon_ids = set(dungeon_ids)
        self.queries = []
        self.result = None

    @contextmanager
    def connection(self):
        yield self

    def execute(self, query, parameters):
        self.queries.append((query, parameters))
        if query != "SELECT 1 FROM dungeon_instances WHERE instance_id=%s":
            raise AssertionError("Breeding persistence must not be accessed")
        self.result = {"exists": 1} if parameters[0] in self.dungeon_ids else None
        return self

    def fetchone(self):
        return self.result


class DungeonReproductionTests(unittest.TestCase):
    def test_public_and_non_dungeon_private_instances_keep_their_policy(self):
        store = RunRegistry({700})
        self.assertFalse(monster_reproduction.dungeon_population(store, 0))
        self.assertEqual(store.queries, [])
        self.assertFalse(monster_reproduction.dungeon_population(store, 701))
        self.assertTrue(monster_reproduction.dungeon_population(store, 700))

    def test_all_room_maps_block_timers_births_and_old_outbox(self):
        store = RunRegistry({700})
        for map_id in (1086, 1234, 9999):
            with self.subTest(map_id=map_id):
                self.assertEqual(
                    monster_reproduction.unpublished(store, map_id, 700), []
                )
                self.assertIsNone(
                    monster_reproduction.attempt(
                        store, {"instance_id": 700}, present=True, indexed=({}, {})
                    )
                )

    def test_world_does_not_publish_or_process_dungeon_birth_outbox(self):
        store = RunRegistry({700})
        world = SimpleNamespace(
            snapshot=lambda: [dict(id=7, map_id=1086, instance_id=700, x=0, y=0, z=0)],
            emit_location=Mock(),
        )
        groups = SimpleNamespace(lock=threading.RLock())
        harvests = SimpleNamespace(lock=threading.RLock(), targets=set())
        result = ecology_mobs.apply(
            store,
            groups,
            harvests,
            world,
            dict(
                kind="publish_reproduction",
                world_epoch="test",
                scope=[1086, 700],
                group_id=3,
                expected_members=[],
            ),
            world_epoch="test",
        )
        self.assertEqual(result, dict(status="applied"))
        world.emit_location.assert_not_called()
        self.assertEqual(
            store.queries,
            [("SELECT 1 FROM dungeon_instances WHERE instance_id=%s", (700,))],
        )

    def test_absent_exterior_attempt_never_enters_breeding_persistence(self):
        store = RunRegistry()
        self.assertIsNone(
            monster_reproduction.attempt(
                store, {"instance_id": 0}, present=False, indexed=({}, {})
            )
        )
        self.assertEqual(store.queries, [])
