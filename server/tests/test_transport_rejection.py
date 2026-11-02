import ast
import os
from pathlib import Path
import unittest
from wakfu_server.dungeon_entry_payment import InsufficientEntranceItems
from wakfu_server.transport_rejection import requires_scene_recovery


class TransportRejectionTests(unittest.TestCase):
    def test_only_uncommitted_atomic_payment_omits_scene_replacement(self):
        missing = InsufficientEntranceItems("missing", reference=15133, quantity=1)
        self.assertFalse(requires_scene_recovery(missing, transition_committed=False))
        for error, committed in (
            (missing, True),
            (missing, None),
            (ValueError("rejected"), False),
            (RuntimeError("attach failed"), True),
        ):
            with self.subTest(error=type(error).__name__, committed=committed):
                self.assertTrue(
                    requires_scene_recovery(error, transition_committed=committed)
                )

    def test_world_rejection_keeps_feedback_without_replacing_unchanged_scene(self):
        from types import SimpleNamespace

        source = Path(
            os.environ.get(
                "TRANSPORT_WORLD_SOURCE",
                Path(__file__).resolve().parents[1] / "local_game_server.py",
            )
        )
        tree = ast.parse(source.read_text())
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If) and "opcode == 12296" in ast.unparse(node.test)
        )
        handler = next(
            handler
            for node in ast.walk(branch)
            if isinstance(node, ast.Try)
            for handler in node.handlers
            if ast.unparse(handler.type) == "ValueError"
        )
        function = ast.FunctionDef(
            name="reject",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="error")],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=handler.body,
            decorator_list=[],
        )
        code = compile(
            ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
            "actual_transport_rejection",
            "exec",
        )

        def packets(error, committed):
            sent = []
            namespace = dict(
                send=lambda connection, service, opcode, body: sent.append(
                    (opcode, body)
                ),
                record=lambda **details: None,
                connection=None,
                service="world",
                character=dict(id=11, map_id=472, instance_id=0),
                account_id=7,
                artifact_action_request=False,
                transport_committed=committed,
                is_dungeon_run=lambda instance: False,
                fixture=lambda opcode: b"scene",
                wire=SimpleNamespace(adapt=lambda *args: b"scene"),
            )
            exec(code, namespace)
            namespace["reject"](error)
            return sent

        missing = InsufficientEntranceItems("missing", reference=15133, quantity=1)
        refused = packets(missing, False)
        committed = packets(missing, True)
        self.assertEqual(len(refused), 1)
        self.assertNotEqual(refused[0][0], 13974)
        self.assertEqual(committed, refused + [(13974, b"scene")])
        self.assertEqual(
            packets(ValueError("unknown transport failure"), False)[-1],
            (13974, b"scene"),
        )
