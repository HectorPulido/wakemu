"""Execute the actual private-return dispatcher branch with domain stubs."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class WithdrawalDispatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        cls.branch = next(
            node
            for node in ast.walk(cls.tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test)
            == "opcode == 12925 and pve_withdrawal_pending is not None"
        )
        cls.code = compile(
            ast.fix_missing_locations(
                ast.Module(body=cls.branch.body, type_ignores=[])
            ),
            "<real-withdraw-return-handler>",
            "exec",
        )
        abandon = next(
            node
            for node in ast.walk(cls.tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 13952 and loaded"
        )
        cls.abandon_code = compile(
            ast.fix_missing_locations(
                ast.Module(
                    body=[
                        ast.For(
                            target=ast.Name(id="_dispatch_once", ctx=ast.Store()),
                            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                            body=abandon.body,
                            orelse=[],
                        )
                    ],
                    type_ignores=[],
                )
            ),
            "<real-shared-abandon-handler>",
            "exec",
        )

    def abandon_context(self):
        fight = SimpleNamespace(id=87, phase="placement")
        shared = SimpleNamespace(
            fight=fight,
            runtime=None,
            participants={1: object(), 2: object()},
            withdrawals={},
        )
        adapter = Mock()
        receipt = dict(
            character={"hp": 42},
            withdrawal=SimpleNamespace(private_packets=[(12238, b"private")]),
        )
        adapter.withdraw_pve.return_value = receipt
        return dict(
            COMBAT_SESSIONS=adapter,
            combat_session="departing-owner",
            character={"id": 4},
            body=b"",
            refresh_shared_combat=lambda: shared,
            fight=fight,
            fight_messages=None,
            group_lease="shared-lease",
            loaded=True,
            pve_withdrawal_pending=None,
            send=Mock(),
            record=Mock(),
            connection=object(),
            service="world",
            wire=SimpleNamespace(chat=lambda *args: b"reject"),
            shared_source=shared,
        )

    def test_actual_placement_abandon_without_runtime_preserves_other_owner(self):
        context = self.abandon_context()
        shared = context["shared_source"]
        other = shared.participants[2]
        exec(self.abandon_code, context)
        context["COMBAT_SESSIONS"].withdraw_pve.assert_called_once_with(
            "departing-owner", context["character"], b""
        )
        self.assertIsNone(context["fight"])
        self.assertIsNone(context["combat_session"])
        self.assertFalse(context["loaded"])
        self.assertIs(
            context["pve_withdrawal_pending"],
            context["COMBAT_SESSIONS"].withdraw_pve.return_value,
        )
        self.assertEqual(shared.fight.phase, "placement")
        self.assertIsNone(shared.runtime)
        self.assertIs(shared.participants[2], other)
        context["send"].assert_called_once_with(
            context["connection"], "world", 12238, b"private"
        )

    def test_actual_malformed_placement_abandon_does_not_withdraw(self):
        context = self.abandon_context()
        context["body"] = b"unexpected"
        exec(self.abandon_code, context)
        context["COMBAT_SESSIONS"].withdraw_pve.assert_not_called()
        self.assertTrue(context["loaded"])
        self.assertEqual(context["combat_session"], "departing-owner")
        self.assertIsNone(context["pve_withdrawal_pending"])

    def context(self):
        receipt = {"withdrawal": SimpleNamespace(fight=SimpleNamespace(id=17))}
        adapter = Mock()
        adapter.session.return_value = "owned-selected-session"
        adapter.return_withdrawn_pve.return_value = {
            "character": {"hp": 42},
            "packets": [(123, b"x")],
        }
        return dict(
            pve_withdrawal_pending=receipt,
            COMBAT_SESSIONS=adapter,
            account_id=1,
            generation="lease",
            character={"id": 9, "x": 1, "y": 2, "z": 3},
            body=b"ack",
            COMBAT_TEST_WP=6,
            connection=object(),
            service="world",
            send=Mock(),
            POSITIONS=Mock(),
            Movement=lambda position: position,
            WORLD=Mock(),
            HAVEN_BAG_EXTERIORS=SimpleNamespace(discard=lambda *_args: None),
            native_transports=SimpleNamespace(
                bootstrap=lambda character: [(234, b"y")]
            ),
            owned_native_bootstrap=lambda character: [(234, b"y")],
            join_world=Mock(),
            mark_static_sync_pending=Mock(),
            record=Mock(),
            loaded=False,
        )

    def test_actual_handler_returns_private_owner_and_clears_pending_only_after_publish(
        self,
    ):
        context = self.context()
        receipt = context["pve_withdrawal_pending"]
        exec(self.code, context)
        context["COMBAT_SESSIONS"].return_withdrawn_pve.assert_called_once_with(
            "owned-selected-session",
            17,
            context["character"],
            b"ack",
            wp=6,
            pending=receipt,
        )
        self.assertIsNone(context["pve_withdrawal_pending"])
        self.assertTrue(context["loaded"])
        self.assertEqual(context["character"]["hp"], 42)
        context["join_world"].assert_called_once()
        context["COMBAT_SESSIONS"].registry.mark_returned.assert_not_called()

    def test_actual_handler_rejected_stale_ack_preserves_pending_and_load_gate(self):
        context = self.context()
        context["COMBAT_SESSIONS"].return_withdrawn_pve.side_effect = ValueError(
            "stale selected lease"
        )
        receipt = context["pve_withdrawal_pending"]
        exec(self.code, context)
        self.assertIs(context["pve_withdrawal_pending"], receipt)
        self.assertFalse(context["loaded"])
        context["send"].assert_not_called()
        context["join_world"].assert_not_called()

    def test_actual_selector_completes_pending_receipt_without_releasing_live_group(
        self,
    ):
        selection = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.If) and ast.unparse(node.test) == "opcode == 13488"
        )
        code = compile(
            ast.fix_missing_locations(ast.Module(body=selection.body, type_ignores=[])),
            "<real-selector-handler>",
            "exec",
        )
        context = self.context()
        context.update(
            body=b"\x00",
            combat_session=None,
            fight=None,
            fight_messages=None,
            group_lease=None,
            spectator_terminal_pending=None,
            STORE=Mock(),
            checkpoint_fight=Mock(),
            release_groups=Mock(),
            replay=Mock(),
            wire=SimpleNamespace(account_kamas=lambda value: b""),
        )
        context["COMBAT_SESSIONS"].recover_withdrawn_pve.return_value = {"hp": 42}
        context["COMBAT_SESSIONS"].registry.lease_generation_active.return_value = True
        # The actual selector imports the existing health helper; a None fight
        # returns before any database access or abort write.
        exec(code, context)
        context["COMBAT_SESSIONS"].recover_withdrawn_pve.assert_called_once()
        context["release_groups"].assert_not_called()
        context["STORE"].clear_character.assert_called_once_with(1, "lease")
        self.assertIsNone(context["pve_withdrawal_pending"])
        self.assertIsNone(context["character"])

    def test_real_selector_last_owner_removes_marker_but_multiowner_keeps_it(self):
        from test_combat_external_markers import sample_shared
        from wakfu_server.combat.combat_external_markers import ExternalFightMarkers

        selection = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.If) and ast.unparse(node.test) == "opcode == 13488"
        )
        publisher = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "publish_external_marker"
        )
        code = compile(
            ast.fix_missing_locations(ast.Module(body=selection.body, type_ignores=[])),
            "<real-selector-marker-handler>",
            "exec",
        )
        for multiowner in (False, True):
            with self.subTest(multiowner=multiowner):
                context = self.context()
                shared = sample_shared()
                shared.withdrawals = {}
                shared.settlement_ready = False
                shared.runtime = Mock()
                import threading

                shared.lock = threading.RLock()
                if multiowner:
                    shared.participants[2] = SimpleNamespace(
                        character_id=18, generation="g2"
                    )
                markers = ExternalFightMarkers()
                markers.update(shared)
                observers = [SimpleNamespace(character_id=33, generation="observer")]
                context.update(
                    body=b"\x00",
                    fight=shared.fight,
                    fight_messages=shared.runtime,
                    combat_session="owner",
                    group_lease=None,
                    spectator_terminal_pending=None,
                    pve_withdrawal_pending=None,
                    STORE=Mock(),
                    checkpoint_fight=Mock(),
                    release_groups=Mock(),
                    replay=Mock(),
                    struct=__import__("struct"),
                    wire=SimpleNamespace(account_kamas=lambda value: b""),
                    COMBAT_TEST=True,
                    COMBAT_GROUPS=SimpleNamespace(
                        lock=threading.RLock(), finish=Mock()
                    ),
                    EXTERNAL_FIGHT_MARKERS=markers,
                    SPECTATORS=SimpleNamespace(
                        sessions=lambda fight_id: tuple(observers)
                    ),
                    refresh_shared_combat=lambda: shared,
                    publish_spectator_state=Mock(
                        side_effect=lambda *args: observers.clear()
                    ),
                )
                context["WORLD"].players = {}
                context["WORLD"].lock = threading.RLock()
                context["COMBAT_SESSIONS"].recover_withdrawn_pve.return_value = {
                    "hp": 42
                }
                context["COMBAT_SESSIONS"].withdraw_pve.return_value = {
                    "character": {"hp": 42}
                }
                context[
                    "COMBAT_SESSIONS"
                ].registry.retire_abandoned_single_owner.return_value = True
                exec(
                    compile(
                        ast.fix_missing_locations(
                            ast.Module(body=[publisher], type_ignores=[])
                        ),
                        "<real-marker-publisher>",
                        "exec",
                    ),
                    context,
                )

                def prepare(*args):
                    shared.fight.phase = "finished"
                    shared.fight.winner = None
                    shared.runtime.abandon_owner = (17, "owner-generation")
                    return {"character": {"hp": 42}, "packets": [(12238, b"terminal")]}

                with patch(
                    "wakfu_server.combat_abandon.prepare", side_effect=prepare
                ), patch(
                    "wakfu_server.combat_abandon.placement_runtime",
                    return_value=shared.runtime,
                ), patch(
                    "wakfu_server.combat_abandon.return_to_world"
                ):
                    exec(code, context)
                if multiowner:
                    self.assertIsNotNone(markers.location(shared.fight.id))
                    context[
                        "COMBAT_SESSIONS"
                    ].registry.retire_abandoned_single_owner.assert_not_called()
                else:
                    self.assertIsNone(markers.location(shared.fight.id))
                    # Simulate poll detaching immediately after terminal publication.
                    # Marker removal must capture its exclusion before that happens.
                    self.assertIsNotNone(
                        context["WORLD"].emit_location_batch.call_args,
                        context["record"].call_args_list,
                    )
                    self.assertIn(
                        (33, "observer"),
                        context["WORLD"].emit_location_batch.call_args.kwargs[
                            "exclude_sessions"
                        ],
                    )
                    self.assertEqual(observers, [])
                    context[
                        "COMBAT_SESSIONS"
                    ].registry.retire_abandoned_single_owner.assert_called_once()

    def test_selector_recovery_precedes_world_replay_and_finalizer_fences_group_release(
        self,
    ):
        source = ast.unparse(self.tree)
        selection = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.If) and ast.unparse(node.test) == "opcode == 23664"
        )
        text = ast.unparse(selection)
        self.assertLess(text.index("recover_withdrawn_pve"), text.index("replay("))
        self.assertIn(
            "if not COMBAT_SESSIONS.registry.lease_generation_active(generation):",
            source,
        )
        abandon = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 13952 and loaded"
        )
        text = ast.unparse(abandon)
        self.assertIn("pve_withdrawal_pending = COMBAT_SESSIONS.withdraw_pve", text)
        self.assertIn("combat_session = group_lease = None", text)
        self.assertIn("loaded = False", text)


if __name__ == "__main__":
    unittest.main()
