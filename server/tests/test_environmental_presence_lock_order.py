"""Local in-memory lock-order reproduction; no database or remote calls."""
import threading
import unittest
from wakfu_server.objectives.environmental_presence import try_positions, capture
from wakfu_server.world import World


class CountedPlayers(dict):
    scans = 0

    def values(self):
        self.scans += 1
        return super().values()


class EnvironmentalWorldLockTests(unittest.TestCase):
    def world(self):
        world = World(lambda *_: None, lambda *_: None, lambda *_: None)
        world.players = CountedPlayers(
            {
                7: (1, None, dict(id=7, map_id=1, instance_id=2, x=3, y=4, z=5)),
                8: (1, None, dict(id=8, map_id=99, instance_id=2, x=8, y=9, z=0)),
            }
        )
        world._presence_generation[(1, 2)] = 4
        return world

    def test_sql_then_world_reader_defers_and_world_then_sql_commit_completes(self):
        world = self.world()
        token = capture(1, 2, world=world)
        sql = threading.Lock()
        sql_held = threading.Event()
        world_held = threading.Event()
        result = {}
        errors = []

        def population():
            try:
                with sql:
                    sql_held.set()
                    if not world_held.wait(0.5):
                        raise AssertionError("Ecology failed to enter World")
                    result["positions"] = try_positions(token, 1, 2)
                    result["scans_before_commit"] = world.players.scans
            except BaseException as e:
                errors.append(repr(e))

        def ecology():
            try:
                if not sql_held.wait(0.5):
                    raise AssertionError("Population failed to own SQL")
                with world.lock:
                    world_held.set()
                    acquired = sql.acquire(timeout=0.5)
                    result["ecology_committed"] = acquired
                    if acquired:
                        sql.release()
            except BaseException as e:
                errors.append(repr(e))

        a = threading.Thread(target=population, daemon=True)
        b = threading.Thread(target=ecology, daemon=True)
        a.start()
        b.start()
        a.join(1)
        b.join(1)
        self.assertFalse(a.is_alive() or b.is_alive())
        self.assertEqual(errors, [])
        self.assertIsNone(result["positions"])
        self.assertEqual(result["scans_before_commit"], 0)
        self.assertTrue(result["ecology_committed"])
        self.assertEqual(try_positions(token, 1, 2), ((3, 4, 5),))

    def test_snapshot_is_scoped_detached_scalar_xyz_and_retryable(self):
        world = self.world()
        token = capture(1, 2, world=world)
        positions = try_positions(token, 1, 2)
        self.assertEqual(positions, ((3, 4, 5),))
        world.players[7][2]["x"] = 20
        self.assertEqual(positions, ((3, 4, 5),))
        self.assertEqual(try_positions(token, 1, 2), ((20, 4, 5),))

    def test_stale_episode_defers_without_scanning_and_reentrant_world_is_valid(self):
        world = self.world()
        old = capture(1, 2, world=world)
        world._presence_generation[(1, 2)] = 5
        self.assertIsNone(try_positions(old, 1, 2))
        self.assertEqual(world.players.scans, 0)
        with world.lock:
            self.assertEqual(
                try_positions(capture(1, 2, world=world), 1, 2), ((3, 4, 5),)
            )
        self.assertIsNone(try_positions(None, 1, 2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
