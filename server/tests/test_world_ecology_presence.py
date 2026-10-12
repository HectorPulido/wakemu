"""Occupancy episodes prevent vacant time from advancing natural monster clocks."""
import unittest
from wakfu_server.world import World


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


if __name__ == "__main__":
    unittest.main()
