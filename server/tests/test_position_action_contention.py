import ast
from source_view import WorldSourcePath as Path
from types import SimpleNamespace
import unittest

from wakfu_server.position_buffer import PositionOwnerBusy


class PositionActionContentionTests(unittest.TestCase):
    def dispatcher(self, flush, requests=(13220, 13220)):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        gate = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "character is not None" in ast.unparse(node.test)
            and any(
                isinstance(child, ast.ExceptHandler)
                and isinstance(child.type, ast.Name)
                and child.type.id == "PositionOwnerBusy"
                for child in ast.walk(node)
            )
        )
        loop = ast.For(
            target=ast.Name(id="opcode", ctx=ast.Store()),
            iter=ast.Name(id="requests", ctx=ast.Load()),
            body=[
                gate,
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="mutations", ctx=ast.Load()),
                            attr="append",
                            ctx=ast.Load(),
                        ),
                        args=[ast.Name(id="opcode", ctx=ast.Load())],
                        keywords=[],
                    )
                ),
            ],
            orelse=[],
        )
        module = ast.Module(body=[loop], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace = dict(
            character={"id": 19},
            account_id=1,
            generation="lease",
            connection=object(),
            service="world",
            requests=list(requests),
            mutations=[],
            notifications=[],
            records=[],
            flush_positions=flush,
            wire=SimpleNamespace(chat=lambda character, message: message),
        )
        namespace["send"] = lambda *args: namespace["notifications"].append(args)
        namespace["record"] = lambda **kwargs: namespace["records"].append(kwargs)
        return compile(module, str(source), "exec"), namespace

    def test_busy_action_does_not_mutate_and_next_request_succeeds(self):
        calls = []

        def flush(**scope):
            calls.append(scope)
            if len(calls) == 1:
                raise PositionOwnerBusy("Position owner is busy; retry checkpoint")

        code, namespace = self.dispatcher(flush)
        exec(code, namespace)
        self.assertEqual(namespace["mutations"], [13220])
        self.assertEqual(len(namespace["notifications"]), 1)
        self.assertEqual(namespace["records"][0]["event"], "request_position_busy")
        self.assertEqual(len(calls), 2)

    def test_other_timeout_remains_terminal(self):
        def flush(**scope):
            raise TimeoutError("Database operation timed out")

        code, namespace = self.dispatcher(flush)
        with self.assertRaisesRegex(TimeoutError, "Database operation"):
            exec(code, namespace)
        self.assertEqual(namespace["mutations"], [])
        self.assertEqual(namespace["notifications"], [])


class CombatReturnAckPositionTests(unittest.TestCase):
    dispatcher = PositionActionContentionTests.dispatcher

    def test_return_ack_skips_generic_flush_but_attack_keeps_position_fence(self):
        calls = []

        def busy_flush(**scope):
            calls.append(scope)
            raise PositionOwnerBusy("return owner is busy")

        code, namespace = self.dispatcher(busy_flush, requests=(12925, 13130))
        exec(code, namespace)
        self.assertEqual(namespace["mutations"], [12925])
        self.assertEqual(len(calls), 1)
        self.assertEqual(namespace["records"][0]["opcode"], 13130)

    def test_actual_return_fence_queues_busy_ack_then_idle_completes_once(self):
        from copy import deepcopy
        from wakfu_server.combat_return_command import PendingEmergencyCommand

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        body = next(
            node.body
            for node in ast.walk(tree)
            if isinstance(node, ast.Try)
            and any(
                isinstance(child, ast.ImportFrom)
                and child.module == "wakfu_server.position_lifecycle"
                for child in node.body
            )
        )
        start = next(
            i
            for i, node in enumerate(body)
            if isinstance(node, ast.ImportFrom)
            and node.module == "wakfu_server.position_lifecycle"
        )
        return_fence = ast.FunctionDef(
            name="return_fence",
            args=ast.arguments(
                posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
            ),
            body=[
                ast.Global(
                    names=[
                        "pending_combat_return",
                        "position_scope",
                        "pending_started",
                        "finish_return",
                    ]
                ),
                *deepcopy(body[start:]),
            ],
            decorator_list=[],
        )
        idle = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "idle"
        )
        branch = next(
            node
            for node in ast.walk(idle)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "pending_combat_return is not None"
        )
        retry = ast.FunctionDef(
            name="retry_return",
            args=ast.arguments(
                posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
            ),
            body=[ast.Global(names=["pending_combat_return"]), deepcopy(branch)],
            decorator_list=[],
        )
        module = ast.fix_missing_locations(
            ast.Module(body=[return_fence, retry], type_ignores=[])
        )
        calls = []
        now = [0.0]
        scope = dict(account_id=1, generation="lease", character_id=19)

        def flush(**actual):
            self.assertEqual(actual, scope)
            calls.append("flush")
            if calls.count("flush") == 1:
                raise PositionOwnerBusy("first fence is busy")

        def complete(**kwargs):
            self.assertEqual(calls[-1], "flush")
            calls.append("complete")

        state = dict(
            account_id=1,
            generation="lease",
            character=dict(id=19),
            fight=SimpleNamespace(id=665),
            abandoned=False,
            shared_return=True,
            shared_state=object(),
            pending_combat_return=None,
            pending_return_command=PendingEmergencyCommand(),
            time=SimpleNamespace(monotonic=lambda: now[0]),
            flush_positions=flush,
            finish_combat_return_after_position_flush=complete,
            release_completed_combat_return_aliases=lambda: calls.append("release"),
            record=lambda **kwargs: None,
            redact=str,
            STORE=SimpleNamespace(current_character_session=lambda *args: True),
        )
        exec(compile(module, str(source), "exec"), state)
        state["return_fence"]()
        self.assertEqual(calls, ["flush"])
        self.assertIsNotNone(state["pending_combat_return"])
        state["retry_return"]()
        self.assertEqual(calls, ["flush"])
        now[0] = 1.0
        state["retry_return"]()
        state["retry_return"]()
        self.assertIsNone(state["pending_combat_return"])
        self.assertEqual(calls, ["flush", "flush", "complete", "release"])
