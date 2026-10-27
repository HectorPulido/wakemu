"""The real global combat guard permits only recognized loaded exterior entry."""
import ast
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from wakfu_server.world import World
from wakfu_server.position_buffer import Positions


class RiftExternalDispatchGuardTests(unittest.TestCase):
    def route(
        self,
        *,
        opcode=12870,
        action=11,
        inside=False,
        loaded=True,
        generation="current",
        dirty_identity=False,
        body=None
    ):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        guard = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.BoolOp)
            and "fight is not None" in ast.unparse(node.test)
            and any(
                isinstance(value, ast.Constant)
                and value.value == "combat_world_action_rejected"
                for statement in node.body
                for value in ast.walk(statement)
            )
        )
        helper = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
                and node.name == "native_exterior_rift_request"
            ),
            None,
        )
        actor = dict(
            id=106,
            account_id=49,
            map_id=1314 if inside else 527,
            instance_id=88 if inside else 0,
            x=-193,
            y=-29,
            z=0,
            direction=2,
        )
        db = SimpleNamespace(
            execute=lambda *args: SimpleNamespace(
                fetchone=lambda: dict(
                    value={"3": dict(entrances=[dict(map_id=527, object_id=33010)])}
                )
            )
        )
        store = SimpleNamespace(connection=lambda: nullcontext(db))
        world = World(
            lambda actor: (1, b"spawn"),
            lambda actor: (2, b"remove"),
            lambda *args: None,
        )
        world.join("current", SimpleNamespace(shutdown=lambda *_: None), actor)
        positions = Positions(
            store, lease_active=lambda *key: key == (49, "current", 106)
        )
        positions.entries[(49, "current", 106)] = dict(
            current=dict(actor, x=-192 if dirty_identity else -193)
        )
        records, reached = [], []
        namespace = dict(
            fight=SimpleNamespace(id=7),
            opcode=opcode,
            loaded=loaded,
            account_id=49,
            generation=generation,
            character=actor,
            STORE=store,
            WORLD=world,
            POSITIONS=positions,
            body=body if body is not None else struct.pack(">qHH", 33010, action, 0),
            record=lambda **row: records.append(row),
            connection=None,
            service="world",
            send=lambda *args: None,
            reached=reached,
            struct=struct,
        )
        loop = ast.For(
            target=ast.Name(id="request", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=[deepcopy(guard)] + ast.parse("reached.append(opcode)").body,
            orelse=[],
        )
        module = ast.fix_missing_locations(
            ast.Module(
                body=([deepcopy(helper)] if helper is not None else []) + [loop],
                type_ignores=[],
            )
        )
        exec(compile(module, str(source), "exec"), namespace)
        return reached, records

    def test_loaded_external_portal_survives_global_guard_with_old_local_combat(self):
        reached, records = self.route()
        self.assertEqual(
            reached, [12870], "global guard blocks the real exterior repair branch"
        )
        self.assertEqual(records, [])

    def test_genuine_inside_other_actions_stale_or_unloaded_identity_stay_blocked(self):
        for options in (
            dict(inside=True),
            dict(opcode=12363),
            dict(opcode=13686),
            dict(action=0),
            dict(action=35),
            dict(loaded=False),
            dict(generation="old"),
            dict(dirty_identity=True),
            dict(body=b"broken"),
            dict(body=struct.pack(">qHH", 33010, 11, 1)),
            dict(body=struct.pack(">qHH", 99999, 11, 0)),
        ):
            with self.subTest(options=options):
                reached, records = self.route(**options)
                self.assertEqual(reached, [])
                self.assertEqual(records[0]["event"], "combat_world_action_rejected")
