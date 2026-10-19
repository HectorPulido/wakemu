"""The real selector branch reports a frozen company without disconnecting."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from psycopg import OperationalError
from wakfu_server.characters.heroes import CompanySelectionRejected


class SelectionRejectionDispatchTests(unittest.TestCase):
    def branch(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Try)
            and any(
                isinstance(handler.type, ast.Name)
                and handler.type.id == "CompanySelectionRejected"
                for handler in node.handlers
            )
        )
        return compile(
            ast.fix_missing_locations(
                ast.Module(
                    body=[
                        ast.For(
                            target=ast.Name(id="attempt", ctx=ast.Store()),
                            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                            body=[branch],
                            orelse=[],
                        )
                    ],
                    type_ignores=[],
                )
            ),
            str(source),
            "exec",
        )

    def test_frozen_selection_sends_native_failure_and_remains_in_selector(self):
        sent, records = [], []

        def rejected(*args):
            raise CompanySelectionRejected("Hero roster is frozen by an active dungeon")

        state = dict(
            STORE=SimpleNamespace(select_character=rejected),
            account_id=11,
            generation="lease",
            request={"character_id": 63},
            character=None,
            CompanySelectionRejected=CompanySelectionRejected,
            connection="socket",
            service="world",
            send=lambda *args: sent.append(args),
            record=lambda **event: records.append(event),
        )
        exec(self.branch(), state)
        self.assertIsNone(state["character"])
        self.assertEqual(sent, [("socket", "world", 23082, b"\x01")])
        self.assertEqual(records[0]["event"], "character_selection_rejected")

    def test_database_and_unknown_failures_remain_errors(self):
        for failure in (
            OperationalError("database unavailable"),
            ValueError("unowned actor"),
            RuntimeError("unexpected"),
        ):
            with self.subTest(failure=type(failure).__name__):
                sent = []

                def rejected(*args):
                    raise failure

                state = dict(
                    STORE=SimpleNamespace(select_character=rejected),
                    account_id=11,
                    generation="lease",
                    request={"character_id": 63},
                    character=None,
                    CompanySelectionRejected=CompanySelectionRejected,
                    connection="socket",
                    service="world",
                    send=lambda *args: sent.append(args),
                    record=lambda **event: None,
                )
                with self.assertRaises(type(failure)):
                    exec(self.branch(), state)
                self.assertEqual(sent, [])
                self.assertIsNone(state["character"])
