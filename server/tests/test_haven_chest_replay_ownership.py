"""Reference account chest state must never escape bootstrap replay."""
import ast
import base64
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class HavenChestReplayOwnershipTests(unittest.TestCase):
    def test_actual_replay_drops_all_captured_compartment_state(self):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        replay = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "replay"
        )
        replay.decorator_list = []
        forbidden = (318, 13929, 13430, 13223, 13716, 13364, 12224, 23627, 13301)
        frames = [
            dict(
                direction="in",
                opcode=opcode,
                body_base64=base64.b64encode(b"foreign account").decode(),
            )
            for opcode in forbidden
        ]
        frames.append(
            dict(
                direction="in",
                opcode=31000,
                body_base64=base64.b64encode(b"unrelated").decode(),
            )
        )
        send = Mock()
        adapt = Mock(return_value=b"owned unrelated")
        namespace = dict(
            FRAMES=frames,
            base64=base64,
            send=send,
            STORE=SimpleNamespace(account_kamas=lambda account: 0),
            wire=SimpleNamespace(adapt=adapt),
            social=SimpleNamespace(adapt=lambda *args, **kwargs: None),
        )
        exec(
            compile(
                ast.Module(body=[replay], type_ignores=[]), "actual_replay", "exec"
            ),
            namespace,
        )
        namespace["replay"]("connection", 0, len(frames), 2)
        send.assert_called_once_with("connection", "world", 31000, b"owned unrelated")
        adapt.assert_called_once()
