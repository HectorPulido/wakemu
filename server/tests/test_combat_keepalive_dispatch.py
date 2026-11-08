"""Native keepalive never enters shared fight persistence or transition locks."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
import unittest
from unittest.mock import Mock


SOURCE = Path(__file__).parents[1] / "local_game_server.py"


class CombatKeepaliveDispatchTests(unittest.TestCase):
    def test_keepalive_trace_does_not_serialize_fight_history(self):
        tree = ast.parse(SOURCE.read_text())
        request = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "RequestTrace"
        )
        snapshot = next(
            keyword.value for keyword in request.keywords if keyword.arg == "snapshot"
        )
        summary = Mock(return_value={"fight_id": 77})
        namespace = dict(
            opcode=33,
            state_summary=summary,
            character=object(),
            fight=object(),
            fight_messages=object(),
        )
        callback = eval(
            compile(ast.Expression(body=deepcopy(snapshot)), str(SOURCE), "eval"),
            namespace,
        )
        for _ in range(2):
            self.assertEqual(callback(), {"keepalive": True})
        summary.assert_not_called()
        namespace["opcode"] = 13510
        self.assertEqual(callback(), {"fight_id": 77})
        summary.assert_called_once_with(
            namespace["character"], namespace["fight"], namespace["fight_messages"]
        )

    def test_six_owner_pings_reply_before_busy_combat_and_close_request_traces(self):
        tree = ast.parse(SOURCE.read_text())
        ping = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If) and ast.unparse(node.test) == "opcode == 33"
        )
        loop = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.While) and ping in node.body
        )
        # Verify placement in the actual dispatcher, not only the extracted
        # handler: no blocking gameplay call can precede this native reply.
        guarded = {
            "committed_travel_holds_request",
            "command_recovery_holds_request",
            "refresh_shared_combat",
            "deliver_rift_transition",
            "deliver_dungeon_transitions",
            "flush_positions",
            "checkpoint_fight",
        }
        preceding = ast.Module(body=loop.body[: loop.body.index(ping)], type_ignores=[])
        calls_before_ping = {
            node.func.id
            for node in ast.walk(preceding)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertFalse(guarded & calls_before_ping)

        function = ast.parse(
            "def dispatch(requests):\n"
            " for connection, body, active_request in requests:\n"
            "  opcode = 33\n"
            " return active_request\n"
        ).body[0]
        function.body[0].body.extend(
            [
                deepcopy(ping),
                *ast.parse("refresh_shared_combat()\ncheckpoint_fight()\n").body,
            ]
        )
        sent = []
        namespace = dict(
            struct=struct,
            service="world",
            send=lambda peer, service, opcode, body: sent.append((peer, opcode, body)),
            refresh_shared_combat=Mock(side_effect=AssertionError("Busy fight lock")),
            checkpoint_fight=Mock(side_effect=AssertionError("Unexpected checkpoint")),
        )
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(module, str(SOURCE), "exec"), namespace)
        requests = [(owner, struct.pack(">i", owner), Mock()) for owner in range(1, 7)]
        self.assertIsNone(namespace["dispatch"](requests))
        self.assertEqual(
            sent,
            [
                packet
                for owner, body, _ in requests
                for packet in (
                    (owner, 23, b"\x01" + body),
                    (owner, 309, struct.pack(">I", 12345)),
                )
            ],
        )
        for _, _, request in requests:
            request.finish.assert_called_once_with()
        namespace["refresh_shared_combat"].assert_not_called()
        namespace["checkpoint_fight"].assert_not_called()

    def test_handshake_still_reaches_its_native_handler(self):
        tree = ast.parse(SOURCE.read_text())
        branches = []
        for opcode in (33, 574):
            branch = next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.If)
                and ast.unparse(node.test) == f"opcode == {opcode}"
            )
            branch = deepcopy(branch)
            branch.orelse = []
            branches.append(branch)
        function = ast.parse(
            "def dispatch(opcode):\n" " for unused in (None,):\n" "  pass\n"
        ).body[0]
        function.body[0].body = branches
        key = Mock()
        key.read_bytes.return_value = b"native-public-key"

        class RuntimePath:
            def __truediv__(self, name):
                self.name = name
                return key

        runtime = RuntimePath()
        send = Mock()
        trace = Mock()
        namespace = dict(
            struct=struct,
            RUNTIME=runtime,
            send=send,
            connection="peer",
            service="world",
            body=b"",
            active_request=trace,
        )
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(module, str(SOURCE), "exec"), namespace)
        namespace["dispatch"](574)
        send.assert_called_once_with(
            "peer", "world", 400, struct.pack(">q", 123456789) + b"native-public-key"
        )
        self.assertEqual(runtime.name, "public-key.der")
        trace.finish.assert_not_called()
