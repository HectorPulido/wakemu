"""Reference effects must not override the owned character after admission."""
import ast
import base64
from contextlib import contextmanager
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class BootstrapReferenceEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        replay = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "replay"
        )
        cls.code = compile(
            ast.fix_missing_locations(ast.Module(body=[replay], type_ignores=[])),
            str(source),
            "exec",
        )

    def run_replay(self, character):
        # The observed foreign visual carrier has family 400, value 0 and a
        # triplet retargeted to the owned player. Its nested source is foreign.
        carrier = bytes.fromhex(
            "0898f4a4af021098f4a4af0218c383052000"
            "2a2108f4ffffffffffffffff0110f8ffffffffffffffff01"
            "18ffffffffffffffffff01308a879301388a879301"
        )
        foreign_visual = (
            struct.pack(">iiBBih", 0, -1, 0, 0, 400, len(carrier))
            + carrier
            + struct.pack(">iiq", 870737239, -1, 27)
        )
        frames = [
            dict(
                direction="in",
                opcode=12666,
                body_base64=base64.b64encode(b"owned-admission").decode(),
            ),
            dict(
                direction="in",
                opcode=12705,
                body_base64=base64.b64encode(foreign_visual).decode(),
            ),
            dict(
                direction="in",
                opcode=12728,
                body_base64=base64.b64encode(b"\x03old").decode(),
            ),
            dict(direction="out", opcode=22296, body_base64=""),
            dict(
                direction="in",
                opcode=13046,
                body_base64=base64.b64encode(b"owned-refresh").decode(),
            ),
        ]
        sent = Mock()
        wire = SimpleNamespace(
            adapt=Mock(side_effect=lambda op, body, *args, **kwargs: body)
        )
        db = SimpleNamespace(execute=Mock(return_value=[]))

        @contextmanager
        def connection():
            yield db

        namespace = dict(
            FRAMES=frames,
            base64=base64,
            struct=struct,
            send=sent,
            wire=wire,
            STORE=SimpleNamespace(
                connection=connection, lock_character=Mock(), account_kamas=lambda _: 0
            ),
            social=SimpleNamespace(adapt=lambda *args, **kwargs: None),
        )
        exec(self.code, namespace)
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.combat_drop_delivery": SimpleNamespace(
                    temporary_section=lambda *args: b"\x00\x00"
                ),
            },
        ):
            namespace["replay"]("peer", 0, len(frames), 2, character, generation=1)
        return sent, wire

    def test_selected_character_keeps_admission_and_refresh_without_foreign_effects(
        self,
    ):
        sent, wire = self.run_replay(dict(id=27, map_id=1134, instance_id=0))
        self.assertEqual(
            [call.args[2:] for call in sent.call_args_list],
            [(12666, b"owned-admission"), (13046, b"owned-refresh")],
        )
        self.assertEqual(
            [call.args[0] for call in wire.adapt.call_args_list], [12666, 13046]
        )

    def test_account_bootstrap_also_discards_reference_effects(self):
        sent, _ = self.run_replay(None)
        self.assertEqual([call.args[2] for call in sent.call_args_list], [12666, 13046])
