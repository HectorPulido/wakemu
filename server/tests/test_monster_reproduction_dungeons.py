"""Dungeon encounters must never enter ecosystem breeding or birth replay."""
from contextlib import contextmanager
import unittest
from unittest.mock import patch

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
                    monster_reproduction.observe(
                        store, map_id, 700, present=True, generation="test", now_ms=1000
                    ),
                    [],
                )
                self.assertEqual(monster_reproduction.pending(store, map_id, 700), [])
                self.assertEqual(
                    monster_reproduction.unpublished(store, map_id, 700), []
                )
                self.assertIsNone(
                    monster_reproduction.attempt(
                        store, {"instance_id": 700}, present=True, indexed=({}, {})
                    )
                )

    def test_tick_does_not_publish_or_process_dungeon_locations(self):
        store = RunRegistry({700})
        with patch.object(monster_reproduction, "observe") as observe, patch.object(
            monster_reproduction, "pending", return_value=[]
        ) as pending, patch.object(
            monster_reproduction, "unpublished", return_value=[]
        ) as unpublished:
            remaining = monster_reproduction.tick(
                store,
                {(1086, 700), (1134, 0), (527, 701)},
                {(9999, 700)},
                generation="test",
                now_ms=1000,
                indexed_by_map={},
                players=[],
                excluded_ids=[],
                emit=lambda *_: self.fail("Unexpected birth"),
            )
            self.assertEqual(remaining, {(1134, 0), (527, 701)})
            self.assertEqual(
                {call.args[1:3] for call in observe.call_args_list}, remaining
            )
            self.assertEqual(
                {call.args[1:3] for call in pending.call_args_list}, remaining
            )
            self.assertEqual(
                {call.args[1:3] for call in unpublished.call_args_list}, remaining
            )

    def test_exterior_observation_still_enters_active_clock_engine(self):
        store = RunRegistry()
        with patch(
            "wakfu_server.monster_active_clocks.observe", return_value=["due"]
        ) as clock:
            self.assertEqual(
                monster_reproduction.observe(
                    store, 527, 0, present=True, generation="test", now_ms=1234
                ),
                ["due"],
            )
            self.assertEqual(clock.call_args.args, (store, 527, 0))
            self.assertEqual(
                clock.call_args.kwargs["table"], "monster_reproduction_timers"
            )
            self.assertEqual(store.queries, [])
