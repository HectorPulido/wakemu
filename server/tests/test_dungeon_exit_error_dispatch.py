"""The actual chat exit branch rejects transient database errors in-session."""
import ast
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


class _ContinueToReturn(ast.NodeTransformer):
    """Adapt the actual loop branch into one callable test invocation."""

    def visit_Continue(self, node):
        return ast.copy_location(ast.Return(value=ast.Constant(True)), node)


class DungeonExitErrorDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SERVER_SOURCE.read_text(encoding="utf-8"))
        cls.session = next(
            node
            for node in cls.tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        cls.exit_branch = next(
            node
            for node in ast.walk(cls.session)
            if isinstance(node, ast.If)
            and any(
                isinstance(child, ast.Constant) and child.value == "!exitdungeon"
                for child in ast.walk(node.test)
            )
        )

    def _invoke_branch(self, error):
        from psycopg import Error as DatabaseError
        from psycopg_pool import PoolTimeout

        names = (
            "text",
            "character",
            "account_id",
            "generation",
            "connection",
            "fight",
            "combat_session",
            "COMBAT_SESSIONS",
            "STORE",
            "POSITIONS",
            "deliver_dungeon_transitions",
            "before_action",
            "record",
            "send",
            "service",
        )
        # The branch's continue returns to the socket loop. In this direct AST
        # harness it returns from the generated callable after its real body.
        branch = _ContinueToReturn().visit(ast.fix_missing_locations(self.exit_branch))
        function = ast.FunctionDef(
            name="_run_exit_branch",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg=name) for name in names],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=[
                ast.While(
                    test=ast.Constant(value=True),
                    body=[branch, ast.Break()],
                    orelse=[],
                ),
                ast.Return(value=ast.Constant(value=False)),
            ],
            decorator_list=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        sent, events = [], []
        namespace = {
            "DatabaseError": DatabaseError,
            "PoolTimeout": PoolTimeout,
            "wire": SimpleNamespace(chat=lambda _character, message: message),
        }
        exec(compile(module, str(SERVER_SOURCE), "exec"), namespace)
        adapter = SimpleNamespace(lookup_character=Mock(return_value=None))
        mocked_exit = ModuleType("dungeon_exit")
        mocked_exit.leave_automatic = Mock(side_effect=error)
        with patch.dict("sys.modules", {"wakfu_server.maps.dungeon_exit": mocked_exit}):
            returned = namespace["_run_exit_branch"](
                text="!exitdungeon",
                character={"id": 10, "name": "Tester", "map_id": 527},
                account_id=1,
                generation="gen-current",
                connection=object(),
                fight=None,
                combat_session=None,
                COMBAT_SESSIONS=adapter,
                STORE=object(),
                POSITIONS=object(),
                deliver_dungeon_transitions=Mock(),
                before_action=object(),
                record=lambda **fields: events.append(fields),
                send=lambda *_args: sent.append(_args),
                service="world",
            )
        self.assertTrue(returned)
        mocked_exit.leave_automatic.assert_called_once()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][1:], ("world", 674, str(error)))
        self.assertEqual(
            events,
            [
                {
                    "event": "dungeon_exit_requested",
                    "actor_id": 10,
                    "instance_id": 0,
                },
                {
                    "event": "dungeon_exit_rejected",
                    "actor_id": 10,
                    "reason": str(error),
                },
            ],
        )

    def test_session_binds_database_exception_types_before_chat_loop(self):
        imports = [
            (node.module, alias.name, alias.asname)
            for node in self.session.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        ]
        self.assertIn(("psycopg", "Error", "DatabaseError"), imports)
        self.assertIn(("psycopg_pool", "PoolTimeout", None), imports)

    def test_exit_branch_rejects_value_database_and_pool_timeout_without_disconnect(
        self,
    ):
        from psycopg import OperationalError
        from psycopg_pool import PoolTimeout

        cases = (
            ValueError("not at an authorized exit"),
            OperationalError("temporary database connection error"),
            PoolTimeout("temporary pool timeout"),
        )
        for error in cases:
            with self.subTest(error=type(error).__name__):
                self._invoke_branch(error)


if __name__ == "__main__":
    unittest.main()
