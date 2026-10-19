"""Exercise the actual selector dispatch branch for terminal shared PvE fights."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from wakfu_server.combat_shared import Session
from wakfu_server.combat_state import Actor, Fight


class TerminalCharacterSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If) and ast.unparse(node.test) == "opcode == 13488"
        )
        loop = ast.For(
            target=ast.Name(id="_dispatch_once", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=branch.body,
            orelse=[],
        )
        cls.code = compile(
            ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])),
            "<actual-terminal-character-selection>",
            "exec",
        )

    def context(self, *, settlement_error=None, local_phase="finished"):
        requester = Session(1, 4, "requester-generation", 1134, 0)
        other = Session(2, 5, "other-generation", 1134, 0)
        fight = Fight(
            377,
            [
                Actor(4, 0, (0, 0, 0), 42, 6, 3, 100, 1, 1, True),
                Actor(5, 0, (1, 0, 0), 42, 6, 3, 90, 1, 2, True),
                Actor(-201, 1, (2, 0, 0), 20, 3, 3, 1, 1),
            ],
            {(0, 0, 0), (1, 0, 0), (2, 0, 0)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0)}},
        )
        fight.phase = local_phase
        fight.winner = 0
        shared = SimpleNamespace(
            fight=fight,
            is_duel=False,
            settlement_ready=False,
            participants={1: requester, 2: other},
        )
        context = {
            "opcode": 13488,
            "account_id": 1,
            "body": b"\x00",
            "spectator_terminal_pending": object(),
            "combat_session": requester,
            "fight": fight,
            "fight_messages": object(),
            "group_lease": "group-lease",
            "character": {"id": 4, "name": "Requester", "hp": 100},
            "shared_selection": None,
            "refresh_shared_combat": Mock(return_value=shared),
            "pending_terminal_world_recovery": None,
            "recover_pending_terminal_world": Mock(),
            "drain_shared_combat": Mock(),
            "complete_test_fight": Mock(),
            "COMBAT_SESSIONS": Mock(),
            "record": Mock(),
            "send": Mock(),
            "connection": object(),
            "service": "world",
            "wire": SimpleNamespace(chat=lambda *_args: b"deferred"),
            "DatabaseError": RuntimeError,
            "PoolTimeout": TimeoutError,
        }

        def finish_existing_fight():
            if settlement_error is not None:
                raise settlement_error
            shared.settlement_ready = True

        context["complete_test_fight"].side_effect = finish_existing_fight
        return context, fight, shared, requester

    def execute(self, context):
        exec(self.code, context)

    def selection_menu_context(self, context):
        context.update(
            combat_session=None,
            fight=None,
            fight_messages=None,
            group_lease=None,
            pve_withdrawal_pending=None,
            pending_terminal_world_recovery=None,
            spectator_terminal_pending=None,
            generation="requester-generation",
            selected=True,
            loaded=True,
            hero_switch_pending=None,
            movement_state=None,
            bag_session=None,
            ranch_session=None,
            checkpoint_fight=Mock(),
            release_groups=Mock(),
            POSITIONS=SimpleNamespace(release=Mock()),
            STORE=SimpleNamespace(
                clear_character=Mock(), account_kamas=Mock(return_value=0)
            ),
            HAVEN_BAG_EXTERIORS=SimpleNamespace(discard=Mock(return_value=None)),
            WORLD=SimpleNamespace(leave=Mock()),
            replay=Mock(),
        )
        context["wire"].account_kamas = lambda _amount: b"account-kamas"
        context["COMBAT_SESSIONS"].registry.lease_generation_active.return_value = True
        return context

    def assert_attached_terminal_deferred(
        self, context, fight, requester, *, withdrawal_attempted=False
    ):
        self.assertIs(context["fight"], fight)
        self.assertIs(context["combat_session"], requester)
        self.assertIsNotNone(context["fight_messages"])
        self.assertIsNotNone(context["group_lease"])
        if withdrawal_attempted:
            context["COMBAT_SESSIONS"].withdraw_pve.assert_called_once()
        else:
            context["COMBAT_SESSIONS"].withdraw_pve.assert_not_called()
        context["COMBAT_SESSIONS"].abandon_shared_pve.assert_not_called()
        context["COMBAT_SESSIONS"].clear_character.assert_not_called()
        context["send"].assert_called_once_with(
            context["connection"], "world", 674, b"deferred"
        )
        records = [call.kwargs for call in context["record"].call_args_list]
        deferred = next(
            record
            for record in records
            if record.get("event") == "combat_terminal_character_selection_deferred"
        )
        self.assertEqual(deferred["fight_id"], fight.id)
        self.assertEqual(deferred["actor_id"], requester.character_id)
        self.assertIs(deferred["native_return_ack"], False)

    def test_finished_pve_with_another_live_owner_retries_settlement_then_defers(self):
        context, fight, shared, requester = self.context()
        self.execute(context)
        context["complete_test_fight"].assert_called_once_with()
        context["drain_shared_combat"].assert_called_once_with()
        context["recover_pending_terminal_world"].assert_not_called()
        self.assertTrue(shared.settlement_ready)
        self.assert_attached_terminal_deferred(context, fight, requester)

    def test_settlement_error_preserves_attached_session_and_does_not_withdraw(self):
        context, fight, _shared, requester = self.context(
            settlement_error=ValueError("durable settlement unavailable")
        )
        self.execute(context)
        context["complete_test_fight"].assert_called_once_with()
        context["drain_shared_combat"].assert_not_called()
        context["recover_pending_terminal_world"].assert_not_called()
        self.assert_attached_terminal_deferred(context, fight, requester)
        deferred = next(
            call.kwargs
            for call in context["record"].call_args_list
            if call.kwargs.get("event")
            == "combat_terminal_character_selection_deferred"
        )
        self.assertEqual(deferred["reason"], "durable settlement unavailable")

    def test_authoritative_refreshed_finished_fight_is_not_misclassified_from_stale_local_phase(
        self,
    ):
        context, fight, shared, requester = self.context(local_phase="active")
        authoritative = Fight(
            fight.id,
            [
                Actor(4, 0, (0, 0, 0), 42, 6, 3, 100, 1, 1, True),
                Actor(5, 0, (1, 0, 0), 42, 6, 3, 90, 1, 2, True),
                Actor(-201, 1, (2, 0, 0), 20, 3, 3, 1, 1),
            ],
            {(0, 0, 0), (1, 0, 0), (2, 0, 0)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0)}},
        )
        authoritative.phase = "finished"
        authoritative.winner = 0

        def refresh():
            context["fight"] = authoritative
            shared.fight = authoritative
            return shared

        context["refresh_shared_combat"].side_effect = refresh
        self.execute(context)
        context["complete_test_fight"].assert_called_once_with()
        self.assert_attached_terminal_deferred(context, authoritative, requester)

    def test_withdrawal_race_that_finishes_fight_defers_after_authoritative_refresh(
        self,
    ):
        context, fight, shared, requester = self.context(local_phase="active")
        refreshes = 0

        def refresh():
            nonlocal refreshes
            refreshes += 1
            if refreshes == 2:
                fight.phase = "finished"
                fight.winner = 0
            return shared

        context["refresh_shared_combat"].side_effect = refresh
        context["COMBAT_SESSIONS"].withdraw_pve.side_effect = ValueError(
            "fight became terminal before withdrawal"
        )
        self.execute(context)
        self.assertEqual(refreshes, 2)
        context["COMBAT_SESSIONS"].withdraw_pve.assert_called_once_with(
            requester, context["character"], b""
        )
        self.assert_attached_terminal_deferred(
            context, fight, requester, withdrawal_attempted=True
        )
        context["complete_test_fight"].assert_not_called()

    def test_withdrawal_error_is_not_swallowed_while_authoritative_fight_is_active(
        self,
    ):
        context, fight, shared, requester = self.context(local_phase="active")
        context["refresh_shared_combat"].return_value = shared
        context["COMBAT_SESSIONS"].withdraw_pve.side_effect = ValueError(
            "ordinary active-fight withdrawal failure"
        )
        with self.assertRaisesRegex(
            ValueError, "ordinary active-fight withdrawal failure"
        ):
            self.execute(context)
        context["COMBAT_SESSIONS"].withdraw_pve.assert_called_once_with(
            requester, context["character"], b""
        )
        self.assertEqual(shared.fight.phase, "active")
        context["send"].assert_not_called()
        context["COMBAT_SESSIONS"].clear_character.assert_not_called()

    def test_after_return_ack_detaches_fight_normal_selection_menu_is_allowed(self):
        context, _fight, _shared, _requester = self.context()
        self.selection_menu_context(context)
        self.execute(context)
        context["complete_test_fight"].assert_not_called()
        context["drain_shared_combat"].assert_not_called()
        context["COMBAT_SESSIONS"].withdraw_pve.assert_not_called()
        context["recover_pending_terminal_world"].assert_not_called()
        context["checkpoint_fight"].assert_called_once_with("aborted")
        context["STORE"].clear_character.assert_called_once_with(
            1, "requester-generation"
        )
        context["replay"].assert_called_once_with(
            context["connection"], 31, 44, 1, generation="requester-generation"
        )
        context["send"].assert_called_once_with(
            context["connection"], "world", 13873, b"account-kamas"
        )
        context["record"].assert_any_call(
            event="returned_to_character_selection", account_id=1
        )

    def test_proven_fresh_world_recovery_then_normal_selection_menu(self):
        context, _fight, shared, _requester = self.context()
        shared.settlement_ready = True
        token = object()
        context["pending_terminal_world_recovery"] = token
        observed_tokens = []

        def recover_proven_fresh_world():
            observed_tokens.append(context["pending_terminal_world_recovery"])
            context["pending_terminal_world_recovery"] = None
            context["combat_session"] = None
            context["fight"] = None
            context["fight_messages"] = None
            context["group_lease"] = None

        context[
            "recover_pending_terminal_world"
        ].side_effect = recover_proven_fresh_world
        self.selection_menu_context(context)
        # Restore the attached state and proof after preparing the post-return
        # menu dependencies; only the helper may consume this exact token.
        context["combat_session"] = _requester
        context["fight"] = shared.fight
        context["fight_messages"] = object()
        context["group_lease"] = "group-lease"
        context["pending_terminal_world_recovery"] = token
        self.execute(context)
        self.assertEqual(observed_tokens, [token])
        context["recover_pending_terminal_world"].assert_called_once_with()
        context["complete_test_fight"].assert_not_called()
        context["drain_shared_combat"].assert_not_called()
        context["COMBAT_SESSIONS"].withdraw_pve.assert_not_called()
        context["STORE"].clear_character.assert_called_once_with(
            1, "requester-generation"
        )
        context["replay"].assert_called_once_with(
            context["connection"], 31, 44, 1, generation="requester-generation"
        )
        context["send"].assert_called_once_with(
            context["connection"], "world", 13873, b"account-kamas"
        )


if __name__ == "__main__":
    unittest.main()
