"""Native account EMOTES and occupation packet layouts."""
import ast
import struct
import time
import unittest
from unittest.mock import Mock
from pathlib import Path
from wakfu_server.characters import emotes


class EmoteWireTests(unittest.TestCase):
    def test_session_dispatch_rejects_without_disconnect_and_refreshes_knowledge(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        module = ast.parse(source.read_text(encoding="utf8"))
        session = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        branch = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 13498 and loaded"
        )
        calls = [node for node in ast.walk(branch) if isinstance(node, ast.Call)]
        self.assertTrue(
            any(
                isinstance(call.func, ast.Name) and call.func.id == "prepare_play"
                for call in calls
            )
        )
        update = next(
            call
            for call in calls
            if isinstance(call.func, ast.Attribute)
            and call.func.attr == "update"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "WORLD"
        )
        self.assertIsNotNone(update)
        handlers = [
            handler
            for node in ast.walk(branch)
            if isinstance(node, ast.Try)
            for handler in node.handlers
        ]
        rejected = next(
            handler
            for handler in handlers
            if isinstance(handler.type, ast.Name) and handler.type.id == "ValueError"
        )
        rejected_calls = [
            node for node in ast.walk(rejected) if isinstance(node, ast.Call)
        ]
        self.assertTrue(
            any(
                isinstance(call.func, ast.Name) and call.func.id == "send"
                for call in rejected_calls
            )
        )
        self.assertTrue(
            any(
                isinstance(call.func, ast.Name)
                and call.func.id == "emote_account_packet"
                for call in rejected_calls
            )
        )

    def test_ordinary_occupation_contains_exact_native_emote(self):
        opcode, body = emotes.occupation(7, 20001)
        self.assertEqual(12088, opcode)
        self.assertEqual(struct.pack(">BhqIiB", 1, 20, 7, 5, 20001, 0), body)

    def test_targeted_occupation_has_native_parameter_name_and_long(self):
        _, body = emotes.occupation(7, 20060, [("targetId", 8)])
        self.assertEqual((1, 20, 7, 25), struct.unpack(">BhqI", body[:15]))
        self.assertEqual(
            struct.pack(">iBI", 20060, 1, 8) + b"targetId" + struct.pack(">q", 8),
            body[15:],
        )

    def test_malformed_play_never_queries_knowledge(self):
        for body in (b"", b"\0" * 11, b"\0" * 13, "invalid"):
            db = Mock()
            with self.assertRaises(ValueError):
                emotes.authorize(db, 1, body)
            db.execute.assert_not_called()

    def test_retained_animation_expires_and_native_stop_has_no_payload(self):
        packet = emotes.occupation(7, 20001)
        self.assertEqual(
            (packet,),
            emotes.retained(
                {"_emote_until": time.monotonic() + 10, "_emote_packet": packet}
            ),
        )
        self.assertEqual(
            (), emotes.retained({"_emote_until": 0, "_emote_packet": packet})
        )
        self.assertEqual((12088, struct.pack(">BhqI", 2, 20, 7, 0)), emotes.stopped(7))

    def test_default_snapshot_is_view_without_knowledge_insert(self):
        db = Mock()
        db.execute.side_effect = [
            Mock(fetchone=lambda: {"value": {"unlock_all": True}}),
            [{"emote_id": 20001}, {"emote_id": 20060}],
            [],  # No separately learned opaque IDs in the default-only fixture.
        ]
        opcode, payload = emotes.snapshot(db, 1)
        self.assertEqual(13873, opcode)
        self.assertEqual(
            (1, 10, len(payload) - 12), struct.unpack(">III", payload[:12])
        )
        self.assertTrue(
            all(
                not call.args[0].startswith("INSERT")
                for call in db.execute.call_args_list
            )
        )
