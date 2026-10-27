"""Occupancy episodes prevent vacant time from advancing natural monster clocks."""
import unittest
import threading
from wakfu_server.world import World
from wakfu_server.objectives import environmental_presence


class WorldEcologyPresenceTests(unittest.TestCase):
    def setUp(self):
        self.world = World(lambda _: b"", lambda _: b"", lambda *_: None)

    def player(self, identity, instance=0):
        return dict(
            id=identity,
            account_id=identity,
            map_id=527,
            instance_id=instance,
            x=0,
            y=0,
            z=0,
        )

    def test_leave_and_reenter_between_worker_snapshots_changes_episode(self):
        self.world.join("first", object(), self.player(1))
        before = self.world.ecology_snapshot()[0]["presence_generation"]
        self.world.leave(1, "first")
        self.world.join("second", object(), self.player(1))
        after = self.world.ecology_snapshot()[0]["presence_generation"]
        self.assertNotEqual(before, after)

    def test_one_remaining_player_preserves_active_episode(self):
        self.world.join("first", object(), self.player(1))
        before = self.world.ecology_snapshot()[0]["presence_generation"]
        self.world.join("second", object(), self.player(2))
        self.world.leave(1, "first")
        self.assertEqual(
            before, self.world.ecology_snapshot()[0]["presence_generation"]
        )

    def test_disconnect_deactivates_presence_before_actor_cleanup(self):
        self.world.join("first", object(), self.player(1))
        before = self.world.ecology_snapshot()[0]["presence_generation"]
        self.assertTrue(self.world.deactivate_ecology(1, "first"))
        self.assertEqual(self.world.ecology_snapshot(), [])
        self.assertEqual(len(self.world.snapshot()), 1)
        self.assertFalse(self.world.snapshot()[0]["_ecology_active"])
        self.world.join("second", object(), self.player(2))
        self.assertNotEqual(
            before, self.world.ecology_snapshot()[0]["presence_generation"]
        )
        self.assertTrue(self.world.leave(1, "first"))
        self.assertEqual(len(self.world.ecology_snapshot()), 1)

    def test_stale_cleanup_cannot_deactivate_replacement_session(self):
        self.world.join("first", object(), self.player(1))
        self.world.join("second", object(), self.player(1))
        self.assertFalse(self.world.deactivate_ecology(1, "first"))
        self.assertFalse(self.world.leave(1, "first"))
        self.assertEqual(len(self.world.ecology_snapshot()), 1)

    def test_instances_have_independent_presence_episodes(self):
        self.world.join("first", object(), self.player(1))
        self.world.join("other", object(), self.player(2, instance=99))
        other_before = next(p for p in self.world.ecology_snapshot() if p["id"] == 2)[
            "presence_generation"
        ]
        self.world.leave(1, "first")
        self.world.join("second", object(), self.player(1))
        other_after = next(p for p in self.world.ecology_snapshot() if p["id"] == 2)[
            "presence_generation"
        ]
        self.assertEqual(other_before, other_after)
        self.assertNotIn("presence_generation", self.world.players[1][2])

    def test_sql_owned_presence_capture_does_not_wait_for_world_commit_lock(self):
        self.world.join("first", object(), self.player(1))
        sql_scope = threading.Lock()
        sql_owned = threading.Event()
        world_owned = threading.Event()
        observations = {}
        errors = []

        def population():
            try:
                with sql_scope:
                    sql_owned.set()
                    if not world_owned.wait(1):
                        raise AssertionError("World commit never acquired its lock")
                    token = environmental_presence.capture(527, 0, world=self.world)
                    observations["captured"] = token
                    observations["current"] = environmental_presence.current(
                        token, 527, 0
                    )
            except BaseException as error:
                errors.append(error)

        def wander_commit():
            try:
                if not sql_owned.wait(1):
                    raise AssertionError("Population never acquired its SQL scope")
                with self.world.lock:
                    world_owned.set()
                    # Reproduce the production order: population owns the SQL
                    # scope; movement owns World and waits for that same scope.
                    acquired = sql_scope.acquire(timeout=1)
                    observations["commit_acquired_sql"] = acquired
                    if acquired:
                        sql_scope.release()
            except BaseException as error:
                errors.append(error)

        threads = [
            threading.Thread(target=population, daemon=True),
            threading.Thread(target=wander_commit, daemon=True),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertTrue(
            observations.get("commit_acquired_sql"),
            "SQL owner waited for World while movement waited for SQL",
        )
        self.assertIsNotNone(observations.get("captured"))
        self.assertTrue(observations.get("current"))

    def test_environmental_tokens_follow_existing_join_disconnect_and_reconnect_episodes(
        self,
    ):
        self.world.join("first", object(), self.player(1))
        initial = environmental_presence.capture(527, 0, world=self.world)
        self.assertIsNotNone(initial)
        self.world.join("second", object(), self.player(2))
        self.assertTrue(self.world.deactivate_ecology(1, "first"))
        self.assertTrue(environmental_presence.current(initial, 527, 0))
        self.assertTrue(self.world.leave(1, "first"))
        self.assertTrue(environmental_presence.current(initial, 527, 0))

        self.world.join("private", object(), self.player(3, instance=99))
        private = environmental_presence.capture(527, 99, world=self.world)
        self.world.join("replacement", object(), self.player(2))
        replacement = environmental_presence.capture(527, 0, world=self.world)
        self.assertFalse(environmental_presence.current(initial, 527, 0))
        self.assertTrue(environmental_presence.current(replacement, 527, 0))
        self.assertFalse(self.world.deactivate_ecology(2, "second"))
        self.assertFalse(self.world.leave(2, "second"))
        self.assertTrue(environmental_presence.current(replacement, 527, 0))
        player = next(p for p in self.world.ecology_snapshot() if p["id"] == 2)
        self.assertEqual(replacement[1], player["presence_generation"])

        self.assertTrue(self.world.leave(2, "replacement"))
        self.assertIsNone(environmental_presence.capture(527, 0, world=self.world))
        self.assertFalse(environmental_presence.current(replacement, 527, 0))
        self.assertTrue(environmental_presence.current(private, 527, 99))

    def test_join_does_not_publish_presence_before_the_player_is_registered(self):
        self.world.join("inactive", object(), self.player(1))
        self.world.deactivate_ecology(1, "inactive")
        before_registration = threading.Event()
        release_spawn = threading.Event()
        read_finished = threading.Event()
        observations = {}
        errors = []

        def paused_spawn(character):
            if character["id"] == 1:
                before_registration.set()
                if not release_spawn.wait(2):
                    raise AssertionError("Paused join was not released")
            return b""

        self.world.spawn = paused_spawn

        def join():
            try:
                self.world.join("new", object(), self.player(2))
            except BaseException as error:
                errors.append(error)

        def capture():
            observations["token_before_entry"] = environmental_presence.capture(
                527, 0, world=self.world
            )
            read_finished.set()

        joining = threading.Thread(target=join, daemon=True)
        reader = threading.Thread(target=capture, daemon=True)
        joining.start()
        try:
            self.assertTrue(before_registration.wait(1))
            reader.start()
            self.assertTrue(
                read_finished.wait(1), "Presence read waited for the paused World join"
            )
            self.assertIsNone(observations["token_before_entry"])
        finally:
            release_spawn.set()
            joining.join(timeout=2)
            if reader.ident is not None:
                reader.join(timeout=2)
        self.assertFalse(joining.is_alive())
        self.assertFalse(reader.is_alive())
        self.assertEqual(errors, [])
        self.assertIn(2, self.world.players)
        self.assertIsNotNone(environmental_presence.capture(527, 0, world=self.world))


if __name__ == "__main__":
    unittest.main()
