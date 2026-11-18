"""Late native scene requests must survive exhausted private-map retry timers."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from wakfu_server.application.dispatch_result import DispatchResult
from wakfu_server.application.session_combat_actions import CombatActionsMixin


class PrivateSceneLateReadyTests(unittest.TestCase):
    def test_bag_request_forces_hydration_after_startup_retries_expire(self):
        peer = SimpleNamespace(
            state=SimpleNamespace(
                character={"id": 42, "map_id": 9},
                static_sync_pending=False,
                static_sync_attempts=3,
            ),
            runtime=SimpleNamespace(record=Mock()),
            sync_loaded_world_snapshot=Mock(return_value=False),
            sync_static_world=Mock(),
        )
        self.assertEqual(
            CombatActionsMixin.handle_captured_view(peer), DispatchResult.FALLTHROUGH
        )
        peer.sync_loaded_world_snapshot.assert_called_once_with(force=True)
        peer.sync_static_world.assert_called_once_with(force=True)
        # Forced hydration does not restart or consume the bounded timer.
        self.assertFalse(peer.state.static_sync_pending)
        self.assertEqual(peer.state.static_sync_attempts, 3)

    def test_public_world_replay_does_not_duplicate_the_static_publication(self):
        peer = SimpleNamespace(
            state=SimpleNamespace(character={"id": 42, "map_id": 527}),
            runtime=SimpleNamespace(record=Mock()),
            sync_loaded_world_snapshot=Mock(return_value=True),
            sync_static_world=Mock(),
        )
        CombatActionsMixin.handle_captured_view(peer)
        peer.sync_static_world.assert_not_called()


if __name__ == "__main__":
    unittest.main()
