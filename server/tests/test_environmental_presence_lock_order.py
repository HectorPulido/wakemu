"""Native scoped presence stays nonblocking under SQL-owned operations."""

import threading
import unittest
from unittest.mock import patch

from wakfu_server.objectives.environmental_presence import capture, try_positions
from wakfu_server.world import World


class EnvironmentalWorldLockTests(unittest.TestCase):
    def world(self):
        world = World(lambda *_: (0, b""), lambda *_: (0, b""), lambda *_: None)
        for actor in (
            dict(
                id=7, account_id=7, map_id=1, instance_id=2, x=3, y=4, z=5, direction=0
            ),
            dict(
                id=8, account_id=8, map_id=99, instance_id=2, x=8, y=9, z=0, direction=0
            ),
        ):
            world.join("lease-" + str(actor["id"]), object(), actor)
        return world

    def test_sql_then_scope_reader_defers_and_scope_then_sql_commit_completes(self):
        world = self.world()
        token = capture(1, 2, world=world)
        sql = threading.Lock()
        sql_held = threading.Event()
        scope_held = threading.Event()
        result = {}
        errors = []

        def population():
            try:
                with sql:
                    sql_held.set()
                    if not scope_held.wait(1):
                        raise AssertionError(
                            "Ecology failed to reserve its native scope"
                        )
                    result["positions"] = try_positions(token, 1, 2)
            except BaseException as error:
                errors.append(repr(error))

        def ecology():
            try:
                if not sql_held.wait(1):
                    raise AssertionError("Population failed to own SQL")
                with world.scope_barrier(1, 2):
                    scope_held.set()
                    acquired = sql.acquire(timeout=1)
                    result["ecology_committed"] = acquired
                    if acquired:
                        sql.release()
            except BaseException as error:
                errors.append(repr(error))

        with patch.object(
            world,
            "captured_players",
            side_effect=AssertionError("Python membership scan"),
        ):
            a = threading.Thread(target=population, daemon=True)
            b = threading.Thread(target=ecology, daemon=True)
            a.start()
            b.start()
            a.join(2)
            b.join(2)
            self.assertFalse(a.is_alive() or b.is_alive())
            self.assertEqual(errors, [])
            self.assertIsNone(result["positions"])
            self.assertTrue(result["ecology_committed"])
            self.assertEqual(try_positions(token, 1, 2), ((3, 4, 5),))

    def test_snapshot_is_scoped_detached_scalar_xyz_and_retryable(self):
        world = self.world()
        token = capture(1, 2, world=world)
        positions = try_positions(token, 1, 2)
        self.assertEqual(positions, ((3, 4, 5),))
        world.refresh_location(
            "lease-7",
            dict(
                id=7, account_id=7, map_id=1, instance_id=2, x=20, y=4, z=5, direction=0
            ),
        )
        self.assertEqual(positions, ((3, 4, 5),))
        self.assertEqual(try_positions(token, 1, 2), ((20, 4, 5),))

    def test_stale_episode_defers_and_same_thread_scope_reader_is_valid(self):
        world = self.world()
        old = capture(1, 2, world=world)
        world.leave(7, "lease-7")
        world.join(
            "replacement",
            object(),
            dict(
                id=7,
                account_id=7,
                map_id=1,
                instance_id=2,
                x=3,
                y=4,
                z=5,
                direction=0,
            ),
        )
        self.assertIsNone(try_positions(old, 1, 2))
        with world.scope_barrier(1, 2):
            self.assertEqual(
                try_positions(capture(1, 2, world=world), 1, 2), ((3, 4, 5),)
            )
        self.assertIsNone(try_positions(None, 1, 2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
