"""The native boss trigger is emitted before the room's actual spawn gate opens."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_story_controller, owned_story_mechanics
from wakfu_server.achievements import storage, tutorial_presentation_once
from wakfu_server.maps import owned_story_encounters


ROOT = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"
CONFIGURATION = ROOT / "astrub-temple-887.configuration.json"


class OwnedStoryBossIntroTests(unittest.TestCase):
    def test_native_boss_intro_uses_pinned_lua_and_gates_boss_room_on_callback(self):
        configuration = json.loads(CONFIGURATION.read_text())
        selected = configuration["topology"]["owned_story_controller"]
        pin = selected["native_sources"]
        raw_native = (ROOT / pin["path"]).read_bytes()
        self.assertEqual(sha256(raw_native).hexdigest(), pin["sha256"])
        native = json.loads(raw_native)
        self.assertEqual(native["scenario_id"], 1722)
        self.assertEqual(native["argument_sources"]["14265"]["boss_trigger"], 23540)

        intro = next(step for step in selected["steps"] if step["id"] == "boss-intro")
        self.assertEqual(intro["kind"], "zone_trigger")
        self.assertEqual(intro["reference"], 23540)
        effect = intro["effects"][0]
        self.assertEqual(effect["event"], 14265)
        self.assertEqual(
            effect["arguments"], [0, "boss_trigger", "owner", 0, 0, 0, 0, 0]
        )

        character = dict(id=7, account_id=3, map_id=887, instance_id=99)
        store = SimpleNamespace()
        db = Mock()
        db.execute.side_effect = AssertionError(
            "The native boss intro must not query room groups or actors"
        )
        with patch.object(
            owned_story_mechanics, "sources", return_value=native
        ), patch.object(
            tutorial_presentation_once, "claim", return_value=True
        ) as claim, patch.object(
            storage, "load_locked", return_value=dict(running=[2166], completed=[])
        ):
            intro_packets = owned_story_mechanics.executor(selected)(
                db, store, character, intro["effects"]
            )
            self.assertEqual(
                intro_packets,
                [
                    (
                        13411,
                        struct.pack(">BiiB", 0, 14265, 1722, 8)
                        + struct.pack(">8q", 0, 23540, 7, 0, 0, 0, 0, 0),
                    )
                ],
            )
            db.execute.assert_not_called()
            claim.assert_called_once()

            completed = {"boss-gate", "boss-intro"}
            callback = owned_story_controller.plan(
                selected,
                completed,
                kind="scenario_complete",
                reference=2,
            )
            self.assertEqual(callback["id"], "boss-intro-done")
            self.assertEqual(callback["effects"][0]["event"], 14288)
            callback_packets = owned_story_mechanics.executor(selected)(
                db, store, character, callback["effects"]
            )
            self.assertEqual(
                callback_packets,
                [(13411, struct.pack(">BiiB", 0, 14288, 1722, 0))],
            )
            db.execute.assert_not_called()
            claim.assert_called_once()

        room = deepcopy(configuration["topology"]["rooms"][-1])
        group_store = SimpleNamespace(character=Mock(return_value=character))
        groups = SimpleNamespace(store=group_store)
        membership = SimpleNamespace(
            fetchall=Mock(return_value=[dict(account_id=3, id=7)])
        )
        gate_db = SimpleNamespace(execute=Mock(return_value=membership))
        with patch.object(
            owned_story_controller,
            "_scope",
            side_effect=lambda *_args: (selected, completed),
        ):
            self.assertFalse(
                owned_story_encounters.can_spawn(
                    gate_db, groups, 99, configuration, room
                )
            )
            completed.add("boss-intro-done")
            self.assertTrue(
                owned_story_encounters.can_spawn(
                    gate_db, groups, 99, configuration, room
                )
            )


if __name__ == "__main__":
    unittest.main()
