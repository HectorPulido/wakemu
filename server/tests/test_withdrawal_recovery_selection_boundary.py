"""Historical withdrawal proof failure keeps both selector connections usable."""
import ast
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import Mock

import test_character_selection_socket_postgres as socket_fixture
import test_terminal_character_selection as terminal_fixture
from wakfu_server.combat_pve_withdraw_store import WithdrawalRecoveryDeferred


class WithdrawalReturnSelectionBoundaryTests(unittest.TestCase):
    def test_selector_return_keeps_pending_owner_and_connection_on_deferred_proof(self):
        fixture = terminal_fixture.TerminalCharacterSelectionTests()
        context, _, _, _ = fixture.context()
        fixture.selection_menu_context(context)
        pending = object()
        context["pve_withdrawal_pending"] = pending
        context[
            "COMBAT_SESSIONS"
        ].recover_withdrawn_pve.side_effect = WithdrawalRecoveryDeferred(
            "Dead withdrawal health no longer matches its exit baseline"
        )
        path = Path(
            os.environ.get("WAKFU_SELECTION_DISPATCH_SOURCE")
            or Path(__file__).resolve().parents[1] / "local_game_server.py"
        )
        source = ast.parse(path.read_text())
        branch = next(
            node
            for node in ast.walk(source)
            if isinstance(node, ast.If) and ast.unparse(node.test) == "opcode == 13488"
        )
        loop = ast.For(
            target=ast.Name(id="_once", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=branch.body,
            orelse=[],
        )
        code = compile(
            ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])),
            str(path),
            "exec",
        )
        exec(code, context)
        self.assertIs(context["pve_withdrawal_pending"], pending)
        self.assertTrue(context["selected"])
        self.assertTrue(context["loaded"])
        context["STORE"].clear_character.assert_not_called()
        context["POSITIONS"].release.assert_not_called()
        context["replay"].assert_not_called()
        context["checkpoint_fight"].assert_not_called()
        context["send"].assert_called_once_with(
            context["connection"], "world", 674, b"deferred"
        )
        self.assertEqual(
            context["record"].call_args.kwargs["event"],
            "withdrawal_selection_return_deferred",
        )


class WithdrawalLoginSelectionSocketTests(
    socket_fixture.CharacterSelectionSocketPostgresTests
):
    def test_deferred_withdrawal_keeps_authenticated_selection_socket_pingable(self):
        self.namespace["reconcile_closed_rift_login"] = lambda *args, **kwargs: None
        self.namespace["COMBAT_SESSIONS"].recover_withdrawn_pve = Mock(
            side_effect=WithdrawalRecoveryDeferred(
                "Historical health proof is incomplete"
            )
        )
        self.send(23664, self.select_body())
        self.assertEqual(self.receive(), (23082, b"\x01"))
        self.receive()  # The ordinary native information packet explains recovery.
        self.send(33, b"withdrawal-deferred")
        self.assertEqual(self.receive(), (23, b"\x01withdrawal-deferred"))
        self.assertEqual(self.receive(), (309, struct.pack(">I", 12345)))
        self.assertTrue(self.store.current_session(self.account, self.generation))
        self.assertFalse(
            self.store.current_character_session(
                self.account, self.generation, self.actor["id"]
            )
        )
        self.assertFalse(
            any(call[0] == "absolute_bootstrap_boundary" for call in self.calls)
        )
        self.assertEqual(
            self.events.get(timeout=10)["event"],
            "withdrawal_character_selection_deferred",
        )
        self.assertTrue(self.failures.empty())


for _name in dir(socket_fixture.CharacterSelectionSocketPostgresTests):
    if _name.startswith("test_"):
        setattr(WithdrawalLoginSelectionSocketTests, _name, None)
