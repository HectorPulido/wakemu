"""Run the actual native13498 dispatcher branch without starting sockets."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from wakfu_server.characters import emotes


def branch(namespace):
    source = Path(__file__).resolve().parents[1] / "local_game_server.py"
    tree = ast.parse(source.read_text())
    node = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.BoolOp)
        and "opcode == 13498" in ast.unparse(n.test)
    )
    function = ast.FunctionDef(
        name="handle",
        args=ast.arguments(
            posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
        ),
        body=copy.deepcopy(node.body),
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(source), "exec"), namespace)
    return namespace["handle"]


class EmoteDispatchTests(unittest.TestCase):
    def context(self):
        return dict(
            STORE=Mock(),
            account_id=2,
            generation="lease",
            character={"id": 7, "name": "Owner"},
            body=b"bad",
            fight=None,
            combat_session=None,
            WORLD=Mock(),
            COMBAT_SESSIONS=Mock(),
            HARVESTS=SimpleNamespace(pending={}),
            PLANTINGS=SimpleNamespace(pending={}),
            connection=object(),
            service="world",
            send=Mock(),
            record=Mock(),
            wire=SimpleNamespace(chat=Mock(return_value=b"rejected")),
        )

    def test_invalid_emote_refreshes_knowledge_and_keeps_handler_alive(self):
        context = self.context()
        with patch.object(
            emotes, "prepare_play", side_effect=ValueError("locked")
        ), patch.object(emotes, "packet", return_value=(13873, b"fresh")):
            branch(context)()
        self.assertEqual(
            [674, 13873], [call.args[2] for call in context["send"].call_args_list]
        )
        context["WORLD"].update.assert_not_called()
        context["record"].assert_called_once_with(
            event="emote_play_rejected", actor_id=7, reason="locked"
        )

    def test_owned_local_combat_is_rejected_even_before_registry_lookup(self):
        context = self.context()
        context["fight"] = object()
        context["COMBAT_SESSIONS"].lookup_character.return_value = None

        def prepare(*args, **options):
            self.assertTrue(options["in_fight"](7))
            raise ValueError("fighting")

        with patch.object(emotes, "prepare_play", side_effect=prepare), patch.object(
            emotes, "packet", return_value=(13873, b"fresh")
        ):
            branch(context)()
        context["WORLD"].update.assert_not_called()
