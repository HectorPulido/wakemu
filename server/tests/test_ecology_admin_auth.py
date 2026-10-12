"""Development chat commands remain administrator-only even if allowlisted."""

import ast
import unittest
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
from contextlib import contextmanager
from pathlib import Path

from wakfu_server.command_permissions import authorize_command


class FakeDatabase:
    def __init__(self, *, admin, allowed):
        self.admin = admin
        self.allowed = allowed

    def execute(self, sql, _params):
        self.sql = sql
        if "FROM accounts" in sql:
            return self
        if "FROM settings" in sql:
            return self
        raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        if "FROM accounts" in self.sql:
            return {"is_admin": self.admin}
        return {"value": self.allowed}


class FakeStore:
    def __init__(self, *, admin, allowed):
        self.db = FakeDatabase(admin=admin, allowed=allowed)

    @contextmanager
    def connection(self):
        yield self.db


class EcologyAdminAuthorizationTests(unittest.TestCase):
    def test_public_command_allowlist_cannot_grant_ecology_admin_commands(self):
        commands = (
            "!nuke",
            "!nuke-all",
            "!genesis",
            "!genesis-all",
            "!eco-status",
            "!nuke-all-flora",
            "!genesis-all-flora",
        )
        store = FakeStore(admin=False, allowed=list(commands))
        for command in commands:
            with self.subTest(command=command), self.assertRaises(PermissionError):
                authorize_command(store, 22, command)

    def test_admin_command_alias_canonicalization_does_not_change_privilege(self):
        store = FakeStore(admin=False, allowed=["!eco-status"])
        with self.assertRaises(PermissionError):
            authorize_command(store, 22, "!ECO-STATUS")

    def test_console_keeps_ecology_commands_argument_free(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server"
            / "maps"
            / "test_console.py"
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "execute"
        )
        namespace = {"__package__": "wakfu_server", "HELP": "test help"}
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"),
            namespace,
        )
        console_execute = namespace["execute"]
        store = FakeStore(admin=True, allowed=[])
        commands = (
            "!nuke",
            "!nuke-all",
            "!genesis",
            "!genesis-all",
            "!eco-status",
            "!nuke-all-flora",
            "!genesis-all-flora",
        )
        for command in commands:
            with self.subTest(command=command), self.assertRaisesRegex(
                ValueError, "test help"
            ):
                console_execute(
                    store, None, 22, "generation", {"id": 4}, command + " extra"
                )


class FloraConsoleRoutingTests(unittest.TestCase):
    def test_flora_commands_forward_runtime_publication_hooks(self):
        path = Path(__file__).resolve().parents[1] / "wakfu_server/maps/test_console.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "execute"
        )
        namespace = {
            "__package__": "wakfu_server",
            "HELP": "test help",
            "_lease": lambda *_args: None,
        }
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"),
            namespace,
        )
        store = FakeStore(admin=True, allowed=[])
        character = {"id": 4, "account_id": 22, "map_id": 1134, "instance_id": 0}
        store.character = lambda *_args: character
        groups, coordination, publish = object(), object(), object()
        players = ({"id": 5},)
        execute_flora = Mock(return_value={"flora": True, "added": 12})
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.ecology_flora_admin": SimpleNamespace(
                    execute=execute_flora
                )
            },
        ):
            for command in ("!nuke-all-flora", "!genesis-all-flora"):
                with self.subTest(command=command):
                    result = namespace["execute"](
                        store,
                        groups,
                        22,
                        "generation",
                        character,
                        command,
                        ecology_players=players,
                        ecology_coordination=coordination,
                        ecology_publish=publish,
                    )
                    self.assertTrue(result["flora"])
                    execute_flora.assert_called_with(
                        store,
                        groups,
                        character,
                        command,
                        players=players,
                        coordination=coordination,
                        publish=publish,
                    )
