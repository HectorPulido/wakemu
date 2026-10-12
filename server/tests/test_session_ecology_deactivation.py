"""Disconnect invalidates ecology presence before blocking logout cleanup."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class SessionEcologyDeactivationTests(unittest.TestCase):
    def test_real_session_finally_deactivates_before_any_cleanup(self):
        path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(path.read_text())
        finalizers = [
            node.finalbody
            for node in ast.walk(tree)
            if isinstance(node, ast.Try)
            and any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "deactivate_ecology"
                for statement in node.finalbody
                for child in ast.walk(statement)
            )
        ]
        self.assertEqual(len(finalizers), 1)
        first = finalizers[0][0]
        calls = []
        world = SimpleNamespace(deactivate_ecology=lambda *args: calls.append(args))
        module = ast.fix_missing_locations(ast.Module(body=[first], type_ignores=[]))
        code = compile(module, str(path), "exec")
        for service, character, generation, expected in (
            ("world", {"id": 41}, "lease", [(41, "lease")]),
            ("auth", {"id": 41}, "lease", []),
            ("world", None, "lease", []),
            ("world", {"id": 41}, None, []),
        ):
            calls.clear()
            exec(
                code,
                dict(
                    WORLD=world,
                    service=service,
                    character=character,
                    generation=generation,
                ),
            )
            self.assertEqual(calls, expected)
