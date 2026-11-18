"""Ordinary login/static bootstrap stays independent of story movement paths."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.application.session_world import WorldSessionMixin
from wakfu_server.application import owned_story_dispatch


class OwnedStorySessionHookTests(unittest.TestCase):
    def test_actual_public_static_bootstrap_never_needs_a_movement_path(self):
        character = dict(id=7, map_id=527, instance_id=0, x=5, y=6, z=0)
        state = SimpleNamespace(
            character=character,
            scene_sync=Mock(),
            connection=SimpleNamespace(),
            generation="qa-generation",
        )
        session = SimpleNamespace(state=state)
        with patch.object(owned_story_dispatch, "arm_movement") as arm:
            WorldSessionMixin.mark_static_sync_pending(session)
        arm.assert_not_called()
        state.scene_sync.arm.assert_called_once()
        self.assertEqual(state.scene_sync.arm.call_args.args[:3], (527, 0, [character]))
        self.assertTrue(state.static_sync_pending)
        self.assertTrue(state.world_snapshot_pending)

    def test_actual_public_scene_sync_has_no_story_state_or_database_requirement(self):
        connection = SimpleNamespace()
        state = SimpleNamespace(
            connection=connection,
            loaded=True,
            character=dict(id=7, map_id=527, instance_id=0, x=5, y=6, z=0),
            fight=None,
            spectator_session=None,
            scene_sync=SimpleNamespace(
                poll=Mock(return_value=()), last_regions=frozenset()
            ),
        )
        runtime = SimpleNamespace(STORE=Mock())
        session = SimpleNamespace(state=state, runtime=runtime)
        WorldSessionMixin.sync_scene_world(session)
        runtime.STORE.connection.assert_not_called()
        state.scene_sync.poll.assert_called_once()

    def test_stale_story_callback_cannot_capture_loaded_event_after_an_admin_exit(self):
        connection = SimpleNamespace(pending_owned_story_scene=(99, "boss-intro-done"))
        state = SimpleNamespace(
            connection=connection, character=dict(id=7, map_id=527, instance_id=0)
        )
        runtime = SimpleNamespace(STORE=Mock())
        self.assertFalse(
            owned_story_dispatch.handle_callback(
                SimpleNamespace(state=state, runtime=runtime)
            )
        )
        self.assertIsNone(connection.pending_owned_story_scene)
        runtime.STORE.connection.assert_not_called()

    def test_nonstory_movement_does_not_create_a_story_arrival(self):
        connection = SimpleNamespace(owned_story_active=False)
        session = SimpleNamespace(state=SimpleNamespace(connection=connection))
        owned_story_dispatch.arm_movement(session, [])
        self.assertFalse(hasattr(connection, "owned_story_arrival"))

    def test_only_declared_story_movement_arms_its_actual_accepted_endpoint(self):
        connection = SimpleNamespace(owned_story_active=True)
        character = dict(id=7, map_id=887, instance_id=99)
        session = SimpleNamespace(
            state=SimpleNamespace(connection=connection, character=character)
        )
        path = [dict(x=0, y=-55, z=12), dict(x=0, y=-56, z=12)]
        with patch.object(owned_story_dispatch.time, "monotonic", return_value=10):
            owned_story_dispatch.arm_movement(session, path)
        self.assertEqual(connection.owned_story_arrival["position"], (0, -56, 12))
        self.assertEqual(connection.owned_story_arrival["instance_id"], 99)
        self.assertAlmostEqual(connection.owned_story_arrival["due"], 10.6)


if __name__ == "__main__":
    unittest.main()
