"""One redistribution request belongs to each real last-player departure."""
import threading
import unittest
from types import SimpleNamespace

from wakfu_server.ecology.world_bridge import EcologyWorldBridge
from wakfu_server.world import World


class WorldIdleEpisodeTests(unittest.TestCase):
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

    def test_last_real_leave_creates_one_episode_and_reentry_exit_creates_another(self):
        self.world.join("first", object(), self.player(1))
        self.world.join("second", object(), self.player(2))
        self.world.leave(1, "first")
        self.assertIsNone(self.world.empty_scope_generation(527, 0))
        self.world.deactivate_ecology(2, "second")
        self.assertIsNone(self.world.empty_scope_generation(527, 0))
        self.world.leave(2, "second")
        episode = self.world.empty_scope_generation(527, 0)
        self.assertIsNotNone(episode)
        expected = [dict(map_id=527, instance_id=0, empty_generation=episode)]
        for _ in range(5):
            self.assertEqual(self.world.empty_scope_snapshot(), expected)
        self.assertFalse(self.world.leave(2, "second"))
        self.assertEqual(self.world.empty_scope_generation(527, 0), episode)
        self.world.join("replacement", object(), self.player(2))
        self.assertIsNone(self.world.empty_scope_generation(527, 0))
        self.assertFalse(self.world.leave(2, "second"))
        self.assertEqual(self.world.empty_scope_snapshot(), [])
        self.world.leave(2, "replacement")
        self.assertGreater(self.world.empty_scope_generation(527, 0), episode)

    def test_bridge_keeps_departed_scope_even_when_no_players_remain(self):
        self.world.join("first", object(), self.player(1))
        self.world.join("private", object(), self.player(2, instance=99))
        self.world.leave(1, "first")
        episode = self.world.empty_scope_generation(527, 0)
        self.world.leave(2, "private")
        bridge = EcologyWorldBridge(
            store=object(),
            world=self.world,
            groups=object(),
            harvests=SimpleNamespace(lock=threading.RLock(), targets={}),
            plantings=SimpleNamespace(growth_seconds=30, open_test_policy=True),
            token="test-token",
        )
        snapshot = bridge.snapshot()
        self.assertEqual(snapshot["players"], [])
        self.assertEqual(snapshot["locations"], [])
        self.assertIn(
            dict(map_id=527, instance_id=0, empty_generation=episode),
            snapshot["empty_scopes"],
        )
