import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server.position_buffer import PositionOwnerBusy


class PositionActionContentionTests(unittest.TestCase):
    def dispatcher(self, flush):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        gate = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "character is not None and opcode != 13331"
            and any(
                isinstance(child, ast.ExceptHandler)
                and isinstance(child.type, ast.Name)
                and child.type.id == "PositionOwnerBusy"
                for child in ast.walk(node)
            )
        )
        loop = ast.For(
            target=ast.Name(id="opcode", ctx=ast.Store()),
            iter=ast.Name(id="requests", ctx=ast.Load()),
            body=[
                gate,
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="mutations", ctx=ast.Load()),
                            attr="append",
                            ctx=ast.Load(),
                        ),
                        args=[ast.Name(id="opcode", ctx=ast.Load())],
                        keywords=[],
                    )
                ),
            ],
            orelse=[],
        )
        module = ast.Module(body=[loop], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace = dict(
            character={"id": 19},
            account_id=1,
            generation="lease",
            connection=object(),
            service="world",
            requests=[13220, 13220],
            mutations=[],
            notifications=[],
            records=[],
            flush_positions=flush,
            wire=SimpleNamespace(chat=lambda character, message: message),
        )
        namespace["send"] = lambda *args: namespace["notifications"].append(args)
        namespace["record"] = lambda **kwargs: namespace["records"].append(kwargs)
        return compile(module, str(source), "exec"), namespace

    def test_busy_action_does_not_mutate_and_next_request_succeeds(self):
        calls = []

        def flush(**scope):
            calls.append(scope)
            if len(calls) == 1:
                raise PositionOwnerBusy("Position owner is busy; retry checkpoint")

        code, namespace = self.dispatcher(flush)
        exec(code, namespace)
        self.assertEqual(namespace["mutations"], [13220])
        self.assertEqual(len(namespace["notifications"]), 1)
        self.assertEqual(namespace["records"][0]["event"], "request_position_busy")
        self.assertEqual(len(calls), 2)

    def test_other_timeout_remains_terminal(self):
        def flush(**scope):
            raise TimeoutError("Database operation timed out")

        code, namespace = self.dispatcher(flush)
        with self.assertRaisesRegex(TimeoutError, "Database operation"):
            exec(code, namespace)
        self.assertEqual(namespace["mutations"], [])
        self.assertEqual(namespace["notifications"], [])
