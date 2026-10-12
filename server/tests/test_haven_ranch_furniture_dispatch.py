"""Execute the real Ranch dispatch and native bootstrap publication order."""
import ast
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import haven_ranch_furniture as domain
from wakfu_server import ecology_feedback


class RanchFurnitureDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(cls.source.read_text())
        cls.branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "opcode == 12766" in ast.unparse(node.test)
            and "ranch_session" in ast.unparse(node.test)
        )
        cls.sync = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "sync_static_world"
        )

    def execute(
        self, opcode=12766, *, action=23, error=None, active=True, combat=False
    ):
        actor = dict(id=41, account_id=7, map_id=1440, instance_id=17)
        emitted, sent, records, fallback = [], [], [], []
        deploy = Mock(
            return_value=dict(packets=[(12259, b"model"), (13664, b"scene")]),
            side_effect=error,
        )
        edit = Mock(
            return_value=dict(
                packets=[(12452, b"model"), (13082, b"remove"), (13664, b"scene")]
            ),
            side_effect=error,
        )
        ns = dict(
            opcode=opcode,
            loaded=True,
            ranch_session=object() if active else None,
            body=struct.pack(">qHH", 123, action, 0),
            fight=object() if combat else None,
            spectator_session=None,
            character=actor,
            account_id=7,
            generation="lease",
            STORE=object(),
            map_geometry=lambda _: {"map_id": 1440},
            cancel_crafting=lambda: None,
            WORLD=SimpleNamespace(emit_location=lambda *args: emitted.append(args)),
            connection=object(),
            service="world",
            send=lambda *args: sent.append(args[2:]),
            record=lambda **event: records.append(event),
            struct=struct,
            fallback=fallback,
        )
        branch = deepcopy(self.branch)
        branch.orelse = [
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="fallback", ctx=ast.Load()),
                        attr="append",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Constant(True)],
                    keywords=[],
                )
            )
        ]
        module = ast.fix_missing_locations(ast.Module(body=[branch], type_ignores=[]))
        with patch.object(domain, "deploy", deploy), patch.object(
            domain, "edit", edit
        ), patch.object(
            ecology_feedback, "information", return_value=(12789, b"error")
        ):
            exec(compile(module, str(self.source), "exec"), ns)
        return deploy, edit, emitted, sent, records, fallback, ns

    def test_native_deploy_and_move_repack_rotate_publish_exact_private_scene(self):
        for opcode, action in ((12766, 0), (12363, 0), (12870, 23), (12870, 29)):
            with self.subTest(opcode=opcode, action=action):
                deploy, edit, emitted, _, records, fallback, ns = self.execute(
                    opcode, action=action
                )
                called = deploy if opcode == 12766 else edit
                called.assert_called_once()
                self.assertIs(called.call_args.kwargs["session"], ns["ranch_session"])
                self.assertEqual(called.call_args.kwargs["geometry"], {"map_id": 1440})
                self.assertTrue(emitted)
                self.assertTrue(all(row[:2] == (1440, 17) for row in emitted))
                self.assertFalse(fallback)
                self.assertEqual(records[-1]["event"], "haven_ranch_furniture_changed")

    def test_invalid_owned_action_is_consumed_and_combat_never_calls_domain(self):
        deploy, _, emitted, sent, records, fallback, _ = self.execute(
            error=ValueError("denied")
        )
        deploy.assert_called_once()
        self.assertFalse(emitted)
        self.assertTrue(sent)
        self.assertFalse(fallback)
        self.assertEqual(records[-1]["event"], "haven_ranch_furniture_rejected")
        deploy, edit, emitted, _, _, fallback, _ = self.execute(combat=True)
        deploy.assert_not_called()
        edit.assert_not_called()
        self.assertFalse(emitted)
        self.assertFalse(fallback)

    def test_nonranch_and_unrelated_generic_action_preserve_existing_dispatch(self):
        for kwargs in ({"active": False}, {"opcode": 12870, "action": 12}):
            deploy, edit, emitted, _, _, fallback, _ = self.execute(**kwargs)
            deploy.assert_not_called()
            edit.assert_not_called()
            self.assertFalse(emitted)
            self.assertTrue(fallback)

    def test_bootstrap_model_precedes_static_scene_and_physical_furniture_follows(self):
        actor = dict(id=41, account_id=7, map_id=1440, instance_id=17)
        sent, records = [], []
        snapshot = Mock(
            return_value=dict(
                packet=(13864, b"areas+furniture"),
                scene_packets=[(13664, b"furniture")],
            )
        )
        ranch = SimpleNamespace(owns=lambda current: current is actor)
        ns = dict(
            character=actor,
            fight=None,
            static_sync_pending=False,
            static_sync_due=0,
            account_id=7,
            generation="lease",
            ranch_session=ranch,
            bag_session=None,
            STORE=SimpleNamespace(
                current_session=lambda *args: True,
                now=lambda: datetime(2026, 10, 12, tzinfo=timezone.utc),
            ),
            active_private_session=lambda: None,
            connection=object(),
            service="world",
            send=lambda *args: sent.append(args[2:]),
            world_static=SimpleNamespace(snapshots=lambda *args, **kwargs: [b"static"]),
            publish_environment_scene=lambda **kwargs: sent.append(("environment",)),
            is_dungeon_run=lambda _: False,
            record=lambda **kwargs: records.append(kwargs),
        )
        function = deepcopy(self.sync)
        function.decorator_list = []
        for index, node in enumerate(function.body):
            if isinstance(node, ast.Nonlocal):
                function.body[index] = ast.Global(names=node.names)
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        with patch.object(domain, "snapshot", snapshot):
            exec(compile(module, str(self.source), "exec"), ns)
            ns["sync_static_world"](force=True)
        self.assertEqual([row[0] for row in sent], [13864, 13984, 13664, "environment"])
        self.assertIs(snapshot.call_args.kwargs["session"], ranch)
        self.assertEqual(snapshot.call_args.kwargs["now_ms"], 1791763200000)
