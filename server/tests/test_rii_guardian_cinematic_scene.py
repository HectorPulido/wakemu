"""The ending replaces the exploration NPC with its original Lua actor."""

import struct
import unittest
from unittest.mock import patch
from wakfu_server.achievements import rii_guardian_battle as guardian


class GuardianCinematicSceneTests(unittest.TestCase):
    def test_remove_static_actor_precedes_original_cinematic(self):
        removal, scene = guardian.cinematic_packets()
        self.assertEqual(
            removal, (12304, b"\x00\x00\x01\x01" + struct.pack(">q", -1706442035962340))
        )
        self.assertEqual(scene, (13411, struct.pack(">BiiB", 0, 22532, 2548, 0)))

    def test_pending_ending_suppresses_only_qualified_dragon(self):
        rows = [
            dict(
                map_id=1387,
                instance_id=0,
                actor_id=-1706442035962340,
                reference_id=5458,
            ),
            dict(map_id=1387, instance_id=0, actor_id=-999, reference_id=5458),
            dict(map_id=1387, instance_id=0, actor_id=-998, reference_id=123),
        ]
        character = dict(map_id=1387, instance_id=0)
        with patch.object(guardian, "pending_cinematic", return_value=True):
            self.assertEqual(
                guardian.visible_dialogue_npcs(None, character, rows), rows[1:]
            )
        with patch.object(guardian, "pending_cinematic", return_value=False):
            self.assertIs(guardian.visible_dialogue_npcs(None, character, rows), rows)
