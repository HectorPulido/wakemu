"""The actual console route submits ecology before foreground checkpoints."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.ecology_admin_jobs import COMMANDS
from wakfu_server.world import World


class EcologyAdminDispatchTests(unittest.TestCase):
    def test_authorized_command_returns_before_flush_and_late_notice_is_generation_fenced(
        self,
    ):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        submit = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "submit_ecology_admin_command"
        )
        command = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "execute_test_command"
        )
        sent, delivered = [], []
        world = World(
            lambda actor: b"spawn",
            lambda actor: b"remove",
            lambda *args: delivered.append(args),
        )
        actor = {
            "id": 7,
            "account_id": 1,
            "map_id": 1134,
            "instance_id": 0,
            "x": 5,
            "y": 6,
            "z": 0,
        }
        world.join("lease", "old-peer", actor)
        request = Mock(
            return_value={
                "handle": "eco-1",
                "status": "running",
                "coalesced": False,
                "message": "Preparando ecología. Puedes seguir jugando.",
            }
        )
        flush = Mock(
            side_effect=AssertionError("ecology submitted after foreground flush")
        )
        namespace = dict(
            ASYNC_ECOLOGY_COMMANDS=COMMANDS,
            ECOLOGY_ADMIN_JOBS=SimpleNamespace(request=request),
            WORLD=world,
            STORE=object(),
            account_id=1,
            generation="lease",
            connection="old-peer",
            service="world",
            character=actor,
            record=Mock(),
            send=lambda *args: sent.append(args),
            flush_positions=flush,
            fight=None,
            combat_session=None,
            PROFILER=SimpleNamespace(profile=lambda name: lambda function: function),
        )
        exec(
            compile(ast.Module(body=[submit], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        names = {
            name
            for node in command.body
            if isinstance(node, ast.Nonlocal)
            for name in node.names
        }
        initial = {name: None for name in names}
        initial["character"] = actor
        namespace["_initial"] = initial
        factory = ast.parse(
            "def build_command():\n    return execute_test_command\n"
        ).body[0]
        factory.body[0:0] = [
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=ast.Subscript(
                    value=ast.Name(id="_initial", ctx=ast.Load()),
                    slice=ast.Constant(name),
                    ctx=ast.Load(),
                ),
            )
            for name in sorted(names)
        ] + [deepcopy(command)]
        module = ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[]))
        exec(compile(module, str(source), "exec"), namespace)
        execute = namespace["build_command"]()
        authority = Mock()
        synchronous = Mock(
            side_effect=AssertionError("synchronous ecology execution reached")
        )
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.test_console": SimpleNamespace(
                    execute=synchronous, parse_target=lambda text: (text, None)
                ),
                "wakfu_server.command_permissions": SimpleNamespace(
                    authorize_command=authority,
                    canonical_command=lambda text: text,
                    is_admin=lambda *args: True,
                ),
            },
        ):
            result = execute("!genesis-all")
        authority.assert_called_once_with(namespace["STORE"], 1, "!genesis-all")
        flush.assert_not_called()
        synchronous.assert_not_called()
        self.assertEqual(result["ecology_job"]["handle"], "eco-1")
        self.assertEqual(sent[0][2], 349)
        subtype, size = struct.unpack(">hh", sent[0][3][:4])
        self.assertEqual((subtype, size), (4, len(sent[0][3][4:])))
        self.assertIn("seguir jugando", sent[0][3][4:].decode("utf-8"))
        notify = request.call_args.kwargs["notify"]
        world.join("replacement", "new-peer", dict(actor))
        notify(
            {"handle": "eco-1", "status": "completed", "message": "Ecología terminada."}
        )
        self.assertEqual(delivered, [])
        self.assertEqual(world.players[7][:2], ("replacement", "new-peer"))
        with self.assertRaisesRegex(ValueError, "Uso"):
            namespace["submit_ecology_admin_command"](
                "peer", "world", 1, "lease", actor, "!genesis", "!genesis extra"
            )
        self.assertIsNone(
            namespace["submit_ecology_admin_command"](
                "peer", "world", 1, "lease", actor, "!position", "!position"
            )
        )
        self.assertEqual(request.call_count, 1)
