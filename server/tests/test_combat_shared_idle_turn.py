"""Exercise the production idle retry gate without starting a socket server."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from wakfu_server.combat_effective_control import effective_server_controlled


class SharedIdleTurnTests(unittest.TestCase):
    def test_only_unpublished_server_turn_is_retried(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        idle = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "idle"
        )
        gate = next(
            n
            for n in ast.walk(idle)
            if isinstance(n, ast.If)
            and isinstance(n.test, ast.BoolOp)
            and any(
                isinstance(c, ast.Expr)
                and isinstance(c.value, ast.Call)
                and isinstance(c.value.func, ast.Name)
                and c.value.func.id == "pass_test_monster_turn"
                for c in n.body
            )
        )
        code = compile(
            ast.fix_missing_locations(ast.Module(body=[gate], type_ignores=[])),
            str(source),
            "exec",
        )
        for phase, controlled, ack, pending, expected in (
            ("active", False, None, [], True),
            ("active", True, None, [], False),
            ("placement", False, None, [], False),
            ("active", False, 3, [], False),
            ("active", False, None, [(1, b"pending")], False),
        ):
            with self.subTest(
                phase=phase, controlled=controlled, ack=ack, pending=bool(pending)
            ):
                calls = []
                env = dict(
                    effective_server_controlled=effective_server_controlled,
                    # The toy fights have no attested ordinary-root manifest;
                    # production correctly grants them no automatic NPC turn.
                    requires_automatic_npc_turn_end=lambda _fight, _actor: False,
                    fight=SimpleNamespace(
                        phase=phase, current=SimpleNamespace(controlled=controlled)
                    ),
                    fight_messages=SimpleNamespace(awaiting_ack=ack, pending=pending),
                    pass_test_monster_turn=lambda: calls.append("run"),
                    refresh_shared_combat=lambda: calls.append("refresh"),
                    drain_shared_combat=lambda: calls.append("drain"),
                )
                exec(code, env)
                self.assertEqual(calls, ["run", "refresh", "drain"] if expected else [])
