"""Execute the actual World building branch without starting a World server."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from psycopg import DatabaseError
from psycopg_pool import PoolTimeout
from wakfu_server import ecology_feedback
from wakfu_server import haven_ranch_buildings as domain
from wakfu_server import haven_ranch_building_wire as wire
from wakfu_server import haven_ranch_building_knowledge as knowledge


class RanchBuildingDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(cls.source.read_text())
        cls.branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "12671" in ast.unparse(node.test)
            and "ranch_session" in ast.unparse(node.test)
        )

    def execute(
        self,
        opcode=12671,
        *,
        error=None,
        broadcast_error=None,
        combat=None,
        active=True,
        loaded=True,
        body=None
    ):
        actor = dict(id=41, account_id=7, map_id=1440, instance_id=17)
        sent, emitted, events, fallback = [], [], [], []
        operate = Mock(
            return_value=dict(packets=[(12558, b"committed")], changed=True),
            side_effect=error,
        )
        cancel = Mock()

        def emit(*args):
            emitted.append(args)
            if broadcast_error is not None:
                raise broadcast_error

        ns = dict(
            opcode=opcode,
            loaded=loaded,
            ranch_session=object() if active else None,
            body=struct.pack(">q", 9001) if body is None else body,
            fight=object() if combat == "fight" else None,
            combat_session=object() if combat == "combat_session" else None,
            spectator_session=object() if combat == "spectator" else None,
            character=actor,
            account_id=7,
            generation="lease",
            STORE=object(),
            cancel_crafting=cancel,
            WORLD=SimpleNamespace(emit_location=emit),
            connection=object(),
            service="world",
            struct=struct,
            DatabaseError=DatabaseError,
            PoolTimeout=PoolTimeout,
            send=lambda *args: sent.append(args[2:]),
            record=lambda **event: events.append(event),
            fallback=fallback,
        )
        branch = deepcopy(self.branch)
        branch.orelse = ast.parse("fallback.append(True)").body
        code = compile(
            ast.fix_missing_locations(ast.Module(body=[branch], type_ignores=[])),
            str(self.source),
            "exec",
        )
        raised = None
        with patch.object(domain, "operate", operate), patch.object(
            ecology_feedback, "information", return_value=(674, b"error")
        ), patch.object(
            knowledge, "packet", return_value=(13873, b"owned")
        ), patch.object(
            knowledge, "scene_packet", return_value=(13864, b"host")
        ):
            try:
                exec(code, ns)
            except (ValueError, DatabaseError, PoolTimeout) as exc:
                raised = exc
        return SimpleNamespace(
            operate=operate,
            cancel=cancel,
            sent=sent,
            emitted=emitted,
            events=events,
            fallback=fallback,
            ns=ns,
            raised=raised,
        )

    def test_all_three_routes_forward_actual_session_and_broadcast_only_private_scene(
        self,
    ):
        for opcode in (12671, 12662, 13480):
            with self.subTest(opcode=opcode):
                result = self.execute(opcode)
                result.operate.assert_called_once_with(
                    result.ns["STORE"],
                    7,
                    "lease",
                    result.ns["character"],
                    opcode,
                    result.ns["body"],
                    session=result.ns["ranch_session"],
                )
                self.assertEqual(
                    result.emitted,
                    [(1440, 17, 12558, b"committed"), (1440, 17, 13864, b"host")],
                )
                self.assertEqual(result.sent, [(13873, b"owned")])
                self.assertFalse(result.fallback)
                self.assertIsNone(result.raised)

    def test_transaction_rejections_send_exact_native_failure_without_broadcast(self):
        for opcode in (12671, 12662, 13480):
            for error in (
                ValueError("foreign or stale"),
                DatabaseError("db"),
                PoolTimeout("pool"),
            ):
                with self.subTest(opcode=opcode, error=type(error).__name__):
                    result = self.execute(opcode, error=error)
                    self.assertEqual(
                        result.sent[0], wire.rejected(opcode, 1440, uid=9001)
                    )
                    self.assertEqual(result.sent[1], (674, b"error"))
                    self.assertFalse(result.emitted)
                    self.assertIsNone(result.raised)
        for body in (b"", struct.pack(">q", -1)):
            result = self.execute(12662, error=ValueError("bad request"), body=body)
            self.assertEqual(result.sent, [(674, b"error")])

    def test_combat_and_spectator_sessions_cannot_mutate_or_cancel_crafting(self):
        for combat in ("fight", "combat_session", "spectator"):
            result = self.execute(combat=combat)
            result.operate.assert_not_called()
            result.cancel.assert_not_called()
            self.assertEqual(result.sent[0], wire.rejected(12671, 1440))
            self.assertFalse(result.emitted)

    def test_missing_ranch_or_unloaded_actor_does_not_enter_domain(self):
        for flags in (dict(active=False), dict(loaded=False)):
            result = self.execute(**flags)
            result.operate.assert_not_called()
            self.assertEqual(result.fallback, [True])
            self.assertFalse(result.sent)

    def test_post_commit_publication_failure_never_forges_transaction_rejection(self):
        for error in (ValueError("publication"), DatabaseError("publication")):
            result = self.execute(broadcast_error=error)
            result.operate.assert_called_once()
            self.assertIs(result.raised, error)
            self.assertEqual(result.emitted, [(1440, 17, 12558, b"committed")])
            self.assertFalse(result.sent)
            self.assertFalse(result.events)
