"""Exercise the production World receive/send branches for opcode 12851."""
import ast
from pathlib import Path
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


def production_node(name, bindings):
    tree = ast.parse(SOURCE.read_text())
    node = next(
        item
        for item in ast.walk(tree)
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == name
    )
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, str(SOURCE), "exec"), bindings)
    return bindings[name]


def opcode_branch(opcode):
    tree = ast.parse(SOURCE.read_text())
    node = next(
        item
        for item in ast.walk(tree)
        if isinstance(item, ast.If) and ast.unparse(item.test) == f"opcode == {opcode}"
    )
    module = ast.fix_missing_locations(ast.Module(body=node.body, type_ignores=[]))
    return compile(module, str(SOURCE), "exec")


class WorldInventoryDeferredJournalTests(unittest.TestCase):
    def test_request_branch_allows_selected_unloaded_actor_and_sends_only_query_reply(
        self,
    ):
        connection = SimpleNamespace()
        character = dict(id=40, hp=471, max_hp=643, x=12, y=13)
        store = Mock()
        world = Mock()
        wire = Mock()
        refresh_owned_character = Mock(
            side_effect=AssertionError("unexpected actor reset")
        )
        send = Mock()
        bindings = dict(
            opcode=12851,
            body=struct.pack(">q", 40),
            account_id=2,
            generation="generation-a",
            selected=True,
            loaded=False,
            character=character,
            STORE=store,
            WORLD=world,
            wire=wire,
            refresh_owned_character=refresh_owned_character,
            connection=connection,
            service="world",
            send=send,
        )
        with patch(
            "wakfu_server.inventory_deferred_journal.query",
            return_value=(12852, b"\x00"),
        ) as query:
            exec(opcode_branch(12851), bindings)

        query.assert_called_once_with(
            store,
            2,
            "generation-a",
            struct.pack(">q", 40),
        )
        send.assert_called_once_with(connection, "world", 12852, b"\x00")
        self.assertEqual(character, dict(id=40, hp=471, max_hp=643, x=12, y=13))
        store.character.assert_not_called()
        world.update.assert_not_called()
        wire.refresh_player.assert_not_called()
        refresh_owned_character.assert_not_called()

    def test_incomplete_owner_context_is_rejected_before_query_or_publication(self):
        cases = (
            {"selected": False},
            {"account_id": None},
            {"generation": None},
            {"character": None},
        )
        for override in cases:
            with self.subTest(override=override):
                send = Mock()
                bindings = dict(
                    opcode=12851,
                    body=struct.pack(">q", 40),
                    account_id=2,
                    generation="generation-a",
                    selected=True,
                    loaded=False,
                    character={"id": 40, "hp": 471, "max_hp": 643},
                    connection=SimpleNamespace(),
                    service="world",
                    send=send,
                )
                bindings.update(override)
                with patch("wakfu_server.inventory_deferred_journal.query") as query:
                    with self.assertRaisesRegex(ValueError, "selected character"):
                        exec(opcode_branch(12851), bindings)
                query.assert_not_called()
                send.assert_not_called()
