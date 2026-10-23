"""Execute actual World herd routes, including their post-commit publication."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from psycopg import DatabaseError
from psycopg_pool import PoolTimeout
import wakfu_server
from wakfu_server import (
    ecology_feedback,
    haven_ranch_herd,
    haven_ranch_building_knowledge,
)


class RanchHerdDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(cls.path.read_text())
        cls.operation = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.If)
            and "13541" in ast.unparse(n.test)
            and "13017" in ast.unparse(n.test)
        )
        cls.acquisition = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.If)
            and ast.unparse(n.test) == "opcode == 13220 and loaded"
        )

    def execute(
        self,
        opcode,
        *,
        result=None,
        error=None,
        scope=None,
        combat=None,
        active=True,
        loaded=True,
        publication_error=None,
        publication_stage="send"
    ):
        actor = dict(
            id=41, account_id=7, map_id=1440, instance_id=17, direction=3, x=4, y=4, z=0
        )
        packets = [(12085, b"rename")] if opcode == 13017 else [(12391, b"placed")]
        outcome = dict(packets=packets, scene_scope=scope, refresh_scene=False)
        if result is not None:
            outcome.update(result)
        operate = Mock(return_value=outcome, side_effect=error)
        sent, emitted, events, fallback = [], [], [], []

        def send(*args):
            sent.append(args[2:])
            if publication_error is not None and publication_stage == "send":
                raise publication_error

        def emit(*args):
            emitted.append(args)
            if publication_error is not None and publication_stage == "emit":
                raise publication_error

        ns = dict(
            opcode=opcode,
            loaded=loaded,
            ranch_session=object() if active else None,
            body=struct.pack(">iq", 1001, 9001)
            if opcode == 13220
            else struct.pack(">q", 9001),
            fight=object() if combat == "fight" else None,
            combat_session=object() if combat == "combat" else None,
            spectator_session=object() if combat == "spectator" else None,
            character=actor,
            account_id=7,
            generation="lease",
            STORE=object(),
            cancel_crafting=Mock(),
            map_geometry=Mock(return_value={"map_id": 1440}),
            WORLD=SimpleNamespace(
                emit_location=emit, request_ranch_scene_refresh=Mock()
            ),
            connection=object(),
            service="world",
            struct=struct,
            DatabaseError=DatabaseError,
            PoolTimeout=PoolTimeout,
            send=send,
            record=lambda **event: events.append(event),
            fallback=fallback,
            sync_static_world=Mock(),
            position=dict(x=4, y=4, z=0),
            refresh_owned_character=lambda saved: dict(saved),
            wire=SimpleNamespace(chat=lambda *args: b"error"),
        )
        branch = deepcopy(self.acquisition if opcode == 13220 else self.operation)
        branch.orelse = ast.parse("fallback.append(True)").body
        loop = ast.For(
            target=ast.Name(id="_once", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(1)], ctx=ast.Load()),
            body=[branch],
            orelse=[],
        )
        code = compile(
            ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])),
            str(self.path),
            "exec",
        )
        raised = None
        scene_packet = Mock(return_value=(13864, b"host"))
        # These unused fallback providers are outside this routing contract;
        # importing their catalogs would turn a pure branch test into a DB load.
        simple_provider = SimpleNamespace(action_class=lambda body: None, use=Mock())
        fallback_providers = {
            "wakfu_server." + name: simple_provider
            for name in (
                "simple_item_actions",
                "companions",
                "scenario_item_actions",
                "book_item_actions",
                "random_item_actions",
            )
        }
        with patch.dict(sys.modules, fallback_providers), patch.object(
            wakfu_server, "companions", simple_provider, create=True
        ), patch.object(haven_ranch_herd, "rename", operate), patch.object(
            haven_ranch_herd, "deploy", operate
        ), patch.object(
            haven_ranch_herd, "repack", operate
        ), patch.object(
            haven_ranch_herd, "use", operate
        ), patch.object(
            haven_ranch_herd, "release", operate, create=True
        ), patch.object(
            haven_ranch_herd, "action_class", return_value="bHz"
        ), patch.object(
            ecology_feedback, "information", return_value=(674, b"error")
        ), patch.object(
            haven_ranch_building_knowledge, "scene_packet", scene_packet
        ):
            try:
                exec(code, ns)
            except (ValueError, DatabaseError, PoolTimeout) as exc:
                raised = exc
        return SimpleNamespace(
            operate=operate,
            sent=sent,
            emitted=emitted,
            events=events,
            fallback=fallback,
            ns=ns,
            raised=raised,
            scene_packet=scene_packet,
        )

    def test_deploy_repack_keep_private_scene_and_account_packets_separate(self):
        for opcode in (13541, 12617):
            with self.subTest(opcode=opcode):
                value = self.execute(
                    opcode,
                    result=dict(
                        packets=[(13754, b"account"), (12657, b"scene")],
                        refresh_scene=True,
                    ),
                )
                self.assertEqual(value.sent, [(13754, b"account"), (12657, b"scene")])
                self.assertEqual(value.emitted, [(1440, 17, 13864, b"host")])
                value.scene_packet.assert_called_once_with(
                    value.ns["STORE"], 7, biome_id=1
                )
                self.assertIs(
                    value.operate.call_args.kwargs["session"], value.ns["ranch_session"]
                )
                self.assertEqual(value.operate.call_args.args[-1], value.ns["body"])
                if opcode == 13541:
                    self.assertEqual(
                        value.operate.call_args.kwargs["geometry"], {"map_id": 1440}
                    )
                value.ns["sync_static_world"].assert_not_called()
                value.ns["WORLD"].request_ranch_scene_refresh.assert_called_once_with(
                    1440, 17, exclude_generation=None
                )

    def test_rename_targets_real_deployed_scene_even_from_another_map(self):
        value = self.execute(13017, scope=(1440, 99))
        self.assertEqual(value.sent, [(12085, b"rename")])
        self.assertEqual(value.emitted, [(1440, 99, 13864, b"host")])
        value.ns["WORLD"].request_ranch_scene_refresh.assert_called_once_with(
            1440, 99, exclude_generation="lease"
        )
        self.assertEqual(value.operate.call_args.args[3], 41)
        self.assertEqual(value.operate.call_args.kwargs, {})
        value = self.execute(13017, scope=(1440, 17))
        self.assertEqual(value.sent, [(12085, b"rename")])
        self.assertEqual(value.emitted, [(1440, 17, 13864, b"host")])
        value = self.execute(13017, scope=None)
        self.assertEqual(value.sent, [(12085, b"rename")])
        self.assertFalse(value.emitted)
        value.ns["WORLD"].request_ranch_scene_refresh.assert_not_called()

    def test_release_updates_owned_state_and_refreshes_only_the_real_private_scene(
        self,
    ):
        value = self.execute(
            13961,
            result=dict(
                packets=[(13754, b"released")],
                scene_scope=(1440, 99),
                refresh_scene=True,
            ),
        )
        self.assertIsNone(value.raised)
        self.assertEqual(value.sent, [(13754, b"released")])
        self.assertEqual(value.emitted, [(1440, 99, 13864, b"host")])
        value.scene_packet.assert_called_once_with(value.ns["STORE"], 7, biome_id=1)
        self.assertIs(value.operate.call_args.args[0], value.ns["STORE"])
        self.assertEqual(
            value.operate.call_args.args[1:4], (7, "lease", value.ns["character"])
        )
        self.assertEqual(value.operate.call_args.args[4], value.ns["body"])
        self.assertIs(
            value.operate.call_args.kwargs["session"], value.ns["ranch_session"]
        )
        value.ns["WORLD"].request_ranch_scene_refresh.assert_called_once_with(
            1440, 99, exclude_generation=None
        )
        self.assertEqual(value.events[-1]["opcode"], 13961)
        self.assertTrue(value.events[-1]["applied"])

    def test_combat_guards_and_domain_rejection_never_publish_scene_changes(self):
        for combat in ("fight", "combat", "spectator"):
            for opcode in (13541, 12617, 13017, 13961):
                value = self.execute(opcode, combat=combat)
                value.operate.assert_not_called()
                value.ns["cancel_crafting"].assert_not_called()
                self.assertFalse(value.emitted)
        for error in (ValueError("foreign"), DatabaseError("db"), PoolTimeout("pool")):
            value = self.execute(13541, error=error)
            self.assertEqual(
                value.sent, [(12391, struct.pack(">qB", 1440, False)), (674, b"error")]
            )
            self.assertFalse(value.emitted)
            value = self.execute(12617, error=error)
            self.assertEqual(
                value.sent, [(12657, struct.pack(">qh", 1440, 99)), (674, b"error")]
            )
            self.assertFalse(value.emitted)
            value = self.execute(13961, error=error)
            self.assertEqual(value.sent, [(674, b"error")])
            self.assertFalse(value.emitted)

    def test_rename_private_publication_failure_is_not_a_transaction_rejection(self):
        for scope in (None, (1440, 17)):
            error = ValueError("publication after commit")
            value = self.execute(
                13017,
                publication_error=error,
                scope=scope,
                publication_stage="send" if scope is None else "emit",
            )
            self.assertIs(value.raised, error)
            self.assertFalse(value.events)
            self.assertEqual(value.sent, [(12085, b"rename")])

    def test_repack_replay_still_refreshes_host_scene_without_broadcasting_owned_delta(
        self,
    ):
        value = self.execute(
            12617,
            result=dict(packets=[(13754, b"owned")], applied=False, refresh_scene=True),
        )
        self.assertEqual(value.sent, [(13754, b"owned")])
        self.assertEqual(value.emitted, [(1440, 17, 13864, b"host")])
        self.assertFalse(value.events[-1]["applied"])
        value.ns["sync_static_world"].assert_not_called()
        value.ns["WORLD"].request_ranch_scene_refresh.assert_called_once_with(
            1440, 17, exclude_generation=None
        )

    def test_real_acquisition_branch_keeps_inventory_and_account_delta_private(self):
        saved = dict(id=41, map_id=527, instance_id=0, direction=0, x=99, y=99, z=0)
        value = self.execute(
            13220,
            result=dict(
                character=saved,
                packets=[(12470, b"debit"), (13754, b"owned")],
                consumed=1,
            ),
        )
        self.assertIsNone(value.raised)
        self.assertEqual(value.sent, [(12470, b"debit"), (13754, b"owned")])
        self.assertFalse(value.emitted)
        self.assertEqual(value.ns["character"]["map_id"], 1440)
        self.assertEqual(value.ns["character"]["instance_id"], 17)
        self.assertEqual(value.operate.call_args.args[-1], value.ns["body"])
        self.assertEqual(value.events[-1]["native_class"], "bHz")
        for combat in ("fight", "combat", "spectator"):
            value = self.execute(
                13220,
                result=dict(character=saved, packets=[], consumed=0),
                combat=combat,
            )
            self.assertTrue(value.operate.call_args.kwargs["in_fight"])

    def test_acquisition_receipt_replay_sends_only_account_snapshot(self):
        saved = dict(id=41, map_id=527, instance_id=0, direction=0)
        value = self.execute(
            13220,
            result=dict(character=saved, packets=[(13873, b"snapshot")], consumed=0),
        )
        self.assertEqual(value.sent, [(13873, b"snapshot")])
        self.assertEqual(value.events[-1]["consumed"], 0)
        self.assertFalse(value.emitted)
        error = DatabaseError("publication after grant")
        value = self.execute(
            13220,
            result=dict(character=saved, packets=[(13754, b"owned")], consumed=1),
            publication_error=error,
        )
        self.assertIs(value.raised, error)
        self.assertFalse(value.events)

    def test_acquisition_domain_failure_returns_feedback_without_inventory_or_herd_delta(
        self,
    ):
        for error in (
            ValueError("invalid UID"),
            DatabaseError("transaction"),
            PoolTimeout("pool"),
        ):
            value = self.execute(13220, error=error)
            self.assertIsNone(value.raised)
            self.assertEqual(value.sent, [(674, b"error")])
            self.assertFalse(value.emitted)
            self.assertEqual(value.events[-1]["event"], "simple_item_action_rejected")
