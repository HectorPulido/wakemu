"""NPC actors remain visible while dialogue menus and stale sessions close."""
import ast
from pathlib import Path
import struct
import unittest

from wakfu_server.maps import npc_dialogue
import test_npc_world


class NpcDialogueDisabledTests(unittest.TestCase):
    def test_actor_masks_all_native_actions_without_removing_appearance(self):
        fixture = test_npc_world.NpcWorldTests()
        fixture.setUp()
        fixture.native["speakers"][0]["actions"].append({"id": 516})
        from wakfu_server.maps.npc_world import spawn

        opcode, payload = spawn(fixture.row, fixture.native)
        self.assertEqual(opcode, 12608)
        self.assertIn(b"Arh Kayuh", payload)
        self.assertTrue(
            payload.endswith(struct.pack(">hhHii", -1, -1, 2, 515, 516) + bytes(21))
        )

    def test_disabled_response_releases_existing_session(self):
        session = npc_dialogue.DialogueSession(nodes={})
        session.node_id, session.speaker_id = 123, 456
        self.assertFalse(npc_dialogue.interactions_enabled())
        self.assertEqual(npc_dialogue.disabled_response(session), (12218, bytes(4)))
        self.assertIsNone(session.node_id)
        self.assertIsNone(session.speaker_id)
        self.assertEqual(npc_dialogue.disabled_response(), (12218, bytes(4)))

    def test_dispatch_closes_before_loading_any_dialogue_catalog(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        guard = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "not npc_dialogue.interactions_enabled()"
        )
        calls = [
            ast.unparse(node.func)
            for node in ast.walk(guard)
            if isinstance(node, ast.Call)
        ]
        self.assertIn("npc_dialogue.disabled_response", calls)
        self.assertNotIn("npc_world.begin", calls)
        self.assertIsInstance(guard.body[-1], ast.Continue)
