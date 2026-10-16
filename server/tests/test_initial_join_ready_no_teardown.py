"""Initial map-ready must not tear down the scene being faded in."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


class JoinReadyTests(unittest.TestCase):
    def run_join(self, opcode, route):
        module = ast.parse(SERVER.read_text())
        branch = next(
            n
            for n in ast.walk(module)
            if isinstance(n, ast.If)
            and isinstance(n.test, ast.BoolOp)
            and isinstance(n.test.values[0], ast.Name)
            and n.test.values[0].id == "selected"
            and any(
                isinstance(v, ast.UnaryOp)
                and isinstance(v.operand, ast.Name)
                and v.operand.id == "loaded"
                for v in n.test.values
            )
        )
        code = compile(
            ast.fix_missing_locations(ast.Module(body=[branch], type_ignores=[])),
            str(SERVER),
            "exec",
        )
        sent = []
        replays = []
        packets = (
            (13256, b""),
            (13974, b"owned-context"),
            (13984, b"static"),
            (12318, b"coords"),
        )
        noop = lambda *args, **kwargs: None
        ns = dict(
            selected=True,
            loaded=False,
            opcode=opcode,
            character={"map_id": 1385, "id": 35, "hp": 60},
            generation=3,
            connection=object(),
            service="world",
            account_id=20,
            position={},
            transports=SimpleNamespace(
                for_map=lambda _: object() if route else None,
                bootstrap=lambda *args: packets,
            ),
            owned_native_bootstrap=lambda *args: packets,
            send=lambda peer, service, mid, body: sent.append((mid, body)),
            join_world=noop,
            resume_settled_shared_combat=noop,
            publish_custom_task_cards=noop,
            mark_static_sync_pending=noop,
            health=SimpleNamespace(packet=lambda *args: b"hp"),
            record=noop,
            replay=lambda *args, **kwargs: replays.append(args),
        )
        exec(code, ns)
        self.assertTrue(ns["loaded"])
        return sent

    def test_ready_keeps_context_without_teardown(self):
        for route in (False, True):
            with self.subTest(route=route):
                sent = self.run_join(14689, route)
                self.assertNotIn((13256, b""), sent)
                self.assertIn((13974, b"owned-context"), sent)
                self.assertIn((13984, b"static"), sent)
                self.assertIn((12436, b"hp"), sent)

    def test_cached_map_action_preserves_existing_bootstrap(self):
        for route in (False, True):
            with self.subTest(route=route):
                self.assertIn((13256, b""), self.run_join(13331, route))


if __name__ == "__main__":
    unittest.main()
