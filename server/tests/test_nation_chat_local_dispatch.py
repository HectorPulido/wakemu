"""Execute native nation selection through the real local-chat dispatcher."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class NationChatLocalDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 12366 and loaded"
        )
        wrapper = ast.For(
            target=ast.Name(id="_once", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=branch.body,
            orelse=[],
        )
        cls.code = compile(
            ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])),
            "<actual-local-chat-handler>",
            "exec",
        )

    def context(self, text):
        channels = Mock()
        channels.minimum_interval.return_value = 0.2
        channels.handle.return_value = 2
        return dict(
            decode_body=lambda *_: {"text": text},
            opcode=12366,
            body=b"",
            loaded=True,
            character={"id": 7},
            account_id=5,
            generation="lease",
            CHANNELS=channels,
            last_chat=0,
            time=SimpleNamespace(monotonic=lambda: 10),
            send=Mock(),
            record=Mock(),
            connection=object(),
            service="world",
            execute_test_command=Mock(),
            WORLD=Mock(),
        )

    def test_public_nation_selection_opens_native_window_without_console(self):
        from wakfu_server.characters import nation_state

        context = self.context("!nacion")
        context.update(STORE=object(), fight=None)
        with patch.object(
            nation_state, "open_selection", return_value=(14006, b"choices")
        ) as opened:
            exec(self.code, context)
        opened.assert_called_once_with(context["STORE"], 5, "lease", 7)
        context["send"].assert_called_once_with(
            context["connection"], "world", 14006, b"choices"
        )
        context["CHANNELS"].handle.assert_not_called()
        context["WORLD"].broadcast.assert_not_called()
        context["execute_test_command"].assert_not_called()

    def test_nation_selection_usage_combat_and_throttling_do_not_open_or_broadcast(
        self,
    ):
        from wakfu_server.characters import nation_state

        for text, fight, last_chat in (
            ("!nacion 30", None, 0),
            ("!nacion", object(), 0),
            ("!nacion", None, 9.9),
        ):
            context = self.context(text)
            context.update(STORE=object(), fight=fight, last_chat=last_chat)
            with patch.object(nation_state, "open_selection") as opened:
                exec(self.code, context)
            opened.assert_not_called()
            context["send"].assert_called_once()
            context["WORLD"].broadcast.assert_not_called()
            context["execute_test_command"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
