"""Focused AST-extracted checks for loaded transition and transport guards."""

import ast
from copy import deepcopy
from pathlib import Path
import unittest

from wakfu_server.position_buffer import PositionOwnerBusy


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _source_tree():
    return ast.parse(SERVER.read_text(encoding="utf8"))


def _loaded_transition_guard():
    matches = [
        node
        for node in ast.walk(_source_tree())
        if isinstance(node, ast.If)
        and "pending_event_ids" in ast.unparse(node.test)
        and "transition_owner_busy" in ast.unparse(node.test)
        and "dungeon_transition_action_deferred"
        in ast.unparse(ast.Module(body=node.body, type_ignores=[]))
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"Expected one loaded transition action guard, got {len(matches)}"
        )
    return matches[0]


def _precommit_busy_handler():
    matches = [
        node
        for node in ast.walk(_source_tree())
        if isinstance(node, ast.ExceptHandler)
        and ast.unparse(node.type) == "PositionOwnerBusy"
        and "request_position_busy"
        in ast.unparse(ast.Module(body=node.body, type_ignores=[]))
        and node.lineno > 16000
    ]
    if len(matches) != 2:
        raise AssertionError(
            f"Expected the two position-busy handlers, got {len(matches)}"
        )
    # The later handler wraps the transport transition; the earlier one fences
    # a different request before the transport branch.
    return max(matches, key=lambda node: node.lineno)


class LocalGameTransitionDispatchGuardTests(unittest.TestCase):
    def _dispatch(self, delivery, opcode):
        guard = deepcopy(_loaded_transition_guard())
        reached = []
        records = []
        scope = {
            "dungeon_delivery": delivery,
            "opcode": opcode,
            "character": {"id": 9},
            "record": lambda **row: records.append(row),
            "reached": reached,
        }
        loop = ast.For(
            target=ast.Name(id="request", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=[guard] + ast.parse("reached.append(opcode)").body,
            orelse=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))
        exec(compile(module, str(SERVER), "exec"), scope)
        return reached, records

    def test_pending_or_busy_transition_blocks_gameplay_but_preserves_control(self):
        blocked = (
            {"pending_event_ids": [81], "state": "pending"},
            {"pending_event_ids": [], "state": "transition_owner_busy"},
        )
        for delivery in blocked:
            for opcode in (13331, 12870):
                with self.subTest(delivery=delivery, opcode=opcode):
                    reached, records = self._dispatch(delivery, opcode)
                    self.assertEqual(reached, [])
                    self.assertEqual(
                        records[0]["event"], "dungeon_transition_action_deferred"
                    )
        for opcode in (314, 23354, 13952, 12366):
            with self.subTest(control_opcode=opcode):
                reached, records = self._dispatch(blocked[0], opcode)
                self.assertEqual(reached, [opcode])
                self.assertEqual(records, [])
        reached, records = self._dispatch(
            {"pending_event_ids": [], "state": "delivered"}, 13331
        )
        self.assertEqual(reached, [13331])
        self.assertEqual(records, [])

    def test_precommit_position_busy_is_recoverable_without_scene_replay(self):
        handler = deepcopy(_precommit_busy_handler())
        sent, records = [], []
        scope = {
            "PositionOwnerBusy": PositionOwnerBusy,
            "record": lambda **row: records.append(row),
            "send": lambda _connection, _service, *packet: sent.append(packet),
            "connection": object(),
            "service": "world",
            "character": {"id": 9},
            "opcode": 13331,
            "Store": object(),
        }
        body = [
            ast.Try(
                body=[
                    ast.Raise(
                        exc=ast.Call(
                            func=ast.Name(id="PositionOwnerBusy", ctx=ast.Load()),
                            args=[ast.Constant("occupied")],
                            keywords=[],
                        ),
                        cause=None,
                    )
                ],
                handlers=[handler],
                orelse=[],
                finalbody=[],
            )
        ]
        module = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
        exec(compile(module, str(SERVER), "exec"), scope)
        self.assertEqual(records[0]["event"], "request_position_busy")
        self.assertEqual(records[0]["opcode"], 13331)
        self.assertTrue(sent)
        self.assertNotIn(13974, [packet[0] for packet in sent])
        self.assertNotIn("owned_native_bootstrap", ast.unparse(handler))


if __name__ == "__main__":
    unittest.main()
