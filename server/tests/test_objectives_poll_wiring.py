"""Execute the actual idle retry block and inspect real worker commit boundaries."""
import ast
from pathlib import Path
import unittest
from psycopg.errors import DeadlockDetected, SerializationFailure


ROOT = Path(__file__).resolve().parent
WORLD = ROOT / "candidate/local_game_server.py"
SERVICE = ROOT / "candidate/service.py"
if not WORLD.exists():
    WORLD = ROOT.parent / "local_game_server.py"
    SERVICE = ROOT.parent / "objectives-service/service.py"


class ObjectivesPollWiringTests(unittest.TestCase):
    def test_only_transaction_conflicts_keep_idle_session_and_coordinators_commit(self):
        tree = ast.parse(WORLD.read_text())
        block = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Try)
            and len(node.body) == 1
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Call)
            and isinstance(node.body[0].value.func, ast.Name)
            and node.body[0].value.func.id == "poll_external_objectives"
        )
        code = compile(
            ast.fix_missing_locations(ast.Module(body=[block], type_ignores=[])),
            str(WORLD),
            "exec",
        )
        events = []
        for kind in (DeadlockDetected, SerializationFailure):

            def poll(kind=kind):
                raise kind("rolled back test transaction")

            env = dict(
                poll_external_objectives=poll,
                DeadlockDetected=DeadlockDetected,
                SerializationFailure=SerializationFailure,
                record=lambda **kw: events.append(kw),
                account_id=130,
                character={"id": 191},
            )
            exec(code, env)
            self.assertEqual(env["character"], {"id": 191})
        self.assertEqual(
            [r["event"] for r in events], ["objectives_poll_transaction_retry"] * 2
        )

        def broken():
            raise ValueError("not a transaction retry")

        env["poll_external_objectives"] = broken
        with self.assertRaises(ValueError):
            exec(code, env)
        # Every coordinator has its own top-level connect context; nested
        # tick_coordinator savepoints cannot accidentally extend those locks.
        service = ast.parse(SERVICE.read_text())
        worker = next(
            n
            for n in service.body
            if isinstance(n, ast.FunctionDef) and n.name == "worker"
        )
        contexts = [
            n
            for n in ast.walk(worker)
            if isinstance(n, ast.With)
            and any(
                isinstance(i.context_expr, ast.Call)
                and isinstance(i.context_expr.func, ast.Name)
                and i.context_expr.func.id == "connect"
                for i in n.items
            )
        ]
        self.assertEqual(len(contexts), 4)
        calls = [
            [ast.unparse(n.value) for n in c.body if isinstance(n, ast.Expr)]
            for c in contexts
        ]
        self.assertIn("assignments.ensure_online", str(calls[1]))
        self.assertIn("hunts.tick", str(calls[2]))
        self.assertIn("tick_pvp(db)", str(calls[3]))
