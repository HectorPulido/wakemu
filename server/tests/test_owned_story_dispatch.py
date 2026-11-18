"""Dispatcher hooks keep optional companion rescue separate from room receipts."""

from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_companion_rescue
from wakfu_server.application import owned_story_dispatch
from wakfu_server import owned_story_controller
from wakfu_server import owned_story_mechanics


PROFILE = (
    Path(__file__).parents[1]
    / "wakfu_server/maps/owned_story_profiles/astrub-temple-887.json"
)


class OwnedStoryDispatchTests(unittest.TestCase):
    def test_school_dresser_uses_verified_clue_descriptor_and_qualifies_room_start(
        self,
    ):
        selected = json.loads(
            (
                Path(__file__).parents[1]
                / "wakfu_server/maps/owned_story_profiles/huppermage-store-1024.json"
            ).read_text()
        )
        native = json.loads(
            (
                Path(__file__).parents[1]
                / "wakfu_server/maps/owned_story_profiles/huppermage-store-1024.native.v1.json"
            ).read_text()
        )
        character = dict(
            id=7, account_id=3, map_id=1024, instance_id=99, x=-1, y=-10, z=0
        )
        db = object()
        completed = set()
        store = SimpleNamespace(
            connection=lambda: nullcontext(db),
            character=Mock(return_value=character),
            now=lambda: datetime(2026, 11, 17, tzinfo=timezone.utc),
        )
        from wakfu_server import world_static
        from wakfu_server.achievements import storage, owned_quest_encounters

        def record_event(_db, _owner, _key, payload):
            completed.add(payload["step"])
            return True

        source = native["reviewed_clue_source"]["source"]
        with (
            patch("wakfu_server.paid_containers._leased_owner"),
            patch("wakfu_server.environment_interactions._guard"),
            patch("wakfu_server.simple_item_actions._idle"),
            patch.object(
                owned_story_controller,
                "_scope",
                side_effect=[
                    (selected, set()),
                    (selected, set()),
                    (selected, completed),
                ],
            ),
            patch.object(owned_story_controller, "pending_scene", return_value=None),
            patch.object(world_static, "objects", return_value=native["objects"]),
            patch.object(storage, "record_event", side_effect=record_event),
            patch.object(
                storage,
                "load_locked",
                return_value={"running": [2784], "completed": []},
            ),
            patch.object(
                owned_quest_encounters,
                "_advance",
                return_value=[(12345, b"objective 5616")],
            ) as advance,
            patch.object(owned_story_mechanics, "allowed", return_value=True),
            patch.object(
                owned_story_mechanics, "_presentation_claim", return_value=True
            ),
            patch.object(
                owned_story_mechanics,
                "authorize_action",
                wraps=owned_story_mechanics.authorize_action,
            ) as authorize,
        ):
            result = owned_story_dispatch.interact(
                store,
                account_id=3,
                generation="generation",
                location=character,
                body=struct.pack(">qHH", 26251, 0, 0),
                loaded=True,
                blocked=False,
            )

        self.assertEqual(source["id"], 26251)
        self.assertEqual(result["step"], "store-clue-inspected")
        self.assertTrue(result["handled"])
        self.assertEqual(result["packets"][0], (12345, b"objective 5616"))
        self.assertEqual(result["packets"][1][0], 13411)
        self.assertEqual(completed, {"store-clue-inspected"})
        self.assertIn(
            "store-clue-inspected", selected["automatic_room_start"]["requires"]
        )
        authorize.assert_called_once()
        self.assertEqual(authorize.call_args.args[4:], (26251, 0))
        advance.assert_called_once()
        self.assertEqual(advance.call_args.args[4], 5616)

    def test_result_reloads_the_committed_position_before_projecting_scene_state(self):
        old = dict(id=7, account_id=3, instance_id=99, map_id=887, x=4, y=2, z=0)
        fresh = dict(old, x=-15, y=-21)
        selected = {"id": "temple"}
        store = SimpleNamespace(character=Mock(return_value=fresh))
        outcome = dict(applied=True, packets=[(13530, b"moved")])
        with patch.object(
            owned_story_controller, "_scope", return_value=(selected, {"done"})
        ) as scope, patch.object(
            owned_story_controller, "pending_scene", return_value=(99, 14265)
        ):
            result = owned_story_dispatch._result(object(), store, old, outcome)

        store.character.assert_called_once_with(3, 7, unittest.mock.ANY)
        self.assertIs(result["character"], fresh)
        self.assertEqual(result["pending_scene"], (99, 14265))
        scope.assert_called_once()
        self.assertEqual(scope.call_args.args[2], fresh)

    def test_cage_visuals_precede_rescue_and_rescue_ignores_completed_room_step(self):
        selected = json.loads(PROFILE.read_text())
        rescue_policy = owned_companion_rescue.policy(selected)
        completed = {"knight-cage"}
        character = dict(
            id=7,
            account_id=3,
            map_id=887,
            instance_id=99,
            x=5,
            y=-59,
            z=12,
        )
        db = object()
        store = SimpleNamespace(
            connection=lambda: nullcontext(db),
            character=Mock(return_value=character),
            now=lambda: datetime(2026, 11, 15, tzinfo=timezone.utc),
        )
        events = []
        admitted = [(12344, b"admitted")]
        visuals = [(13411, b"native cage visuals")]
        rescued = [(13832, b"rescue completion")]

        def record_admit(*args):
            events.append("admit")
            return admitted

        def record_visuals(*args):
            events.append("visuals")
            return visuals

        def record_rescue(*args):
            events.append("rescue")
            return rescued

        def record_controller(*args, **kwargs):
            events.append("room controller")
            return dict(applied=False, packets=[], step=None)

        with (
            patch("wakfu_server.paid_containers._leased_owner"),
            patch("wakfu_server.environment_interactions._guard"),
            patch("wakfu_server.simple_item_actions._idle"),
            patch.object(
                owned_story_controller,
                "_scope",
                return_value=(selected, completed),
            ),
            patch.object(owned_story_controller, "pending_scene", return_value=None),
            patch.object(owned_companion_rescue, "policy", return_value=rescue_policy),
            patch.object(
                owned_companion_rescue, "admit", side_effect=record_admit
            ) as admit,
            patch.object(
                owned_story_mechanics, "object_visuals", side_effect=record_visuals
            ),
            patch.object(
                owned_companion_rescue, "interact", side_effect=record_rescue
            ) as rescue,
            patch.object(
                owned_story_controller, "interact", side_effect=record_controller
            ),
        ):
            result = owned_story_dispatch.interact(
                store,
                account_id=3,
                generation="generation",
                location=character,
                body=struct.pack(">qHH", 23583, 0, 0),
                loaded=True,
                blocked=False,
            )

        self.assertEqual(events, ["admit", "visuals", "rescue", "room controller"])
        admit.assert_called_once()
        rescue.assert_called_once()
        self.assertEqual(result["packets"], visuals + admitted + rescued)
        self.assertTrue(result["handled"])


if __name__ == "__main__":
    unittest.main()
