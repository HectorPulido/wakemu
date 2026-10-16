"""Transport joins defer dynamic creates until the single ready/fallback replay."""
import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


class ExtractFunctions(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        return ast.copy_location(ast.Pass(), node)

    def visit_Nonlocal(self, node):
        return ast.copy_location(ast.Global(names=node.names), node)


class TransportSceneHydrationTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SERVER.read_text())
        names = {
            "join_world",
            "send_loaded_world_snapshot",
            "sync_loaded_world_snapshot",
        }
        functions = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name in names
        ]
        for node in functions:
            node.decorator_list = []
        code = ast.fix_missing_locations(
            ExtractFunctions().visit(ast.Module(body=functions, type_ignores=[]))
        )
        self.sent = []
        empty = lambda *a, **k: ()
        character = dict(id=29, account_id=1, map_id=527, instance_id=0)
        self.ns = dict(
            STORE=NS(
                connection=lambda: nullcontext(object()),
                current_session=lambda *a: True,
            ),
            ensure_all_learned=lambda *a: {"packets": ()},
            HAVEN_BAG_EXTERIORS=NS(snapshots=empty),
            PLANTINGS=NS(snapshots=lambda *a, **k: ((20001, b"plant"),)),
            npc_world=NS(load_scene=empty),
            npc_placements=NS(load_scene=empty),
            heroes=NS(ensure_company_party=lambda *a: {"heroes": ()}),
            hero_wire=NS(company=lambda *a, **k: (20002, b"company")),
            WORLD=NS(join=Mock(), resynchronize=Mock(return_value=True)),
            COMBAT_TEST=True,
            COMBAT_GROUPS=NS(
                lock=nullcontext(),
                available=lambda *a: [{"members": (), "key": (527, 0, 9)}],
            ),
            spawn_group=lambda *a, **k: b"group",
            admin_removed_packets=empty,
            defeated_snapshot=empty,
            monster_corpse_snapshot=empty,
            HARVESTS=NS(availability_snapshot=empty),
            EXTERNAL_FIGHT_MARKERS=NS(world_snapshots=empty),
            refresh_party=Mock(),
            refresh_guild=Mock(),
            send_planting_context=Mock(),
            send=lambda peer, service, mid, body: self.sent.append((mid, body)),
            character=character,
            loaded=True,
            account_id=1,
            generation=2,
            connection=object(),
            service="world",
            fight=None,
            combat_session=None,
            sync_static_world=Mock(),
            world_snapshot_pending=True,
            world_snapshot_due=10,
            world_snapshot_identity=(29, 2, 527, 0),
            time=NS(monotonic=lambda: 11),
            record=Mock(),
        )
        exec(compile(code, str(SERVER), "exec"), self.ns)

    def join(self, **kwargs):
        self.ns["join_world"](2, self.ns["connection"], self.ns["character"], **kwargs)

    def assert_dynamic_count(self, count):
        self.assertEqual(self.sent.count((20001, b"plant")), count)
        self.assertEqual(self.sent.count((12608, b"group")), count)

    def test_transport_join_then_repeated_ready_publishes_dynamic_entities_once(self):
        self.join(defer_scene_snapshot=True)
        self.assert_dynamic_count(0)
        self.ns["WORLD"].join.assert_called_once()
        self.assertIn((20002, b"company"), self.sent)
        self.assertTrue(self.ns["sync_loaded_world_snapshot"](force=True))
        self.assertFalse(self.ns["sync_loaded_world_snapshot"](force=True))
        self.assertFalse(self.ns["sync_loaded_world_snapshot"]())
        self.assert_dynamic_count(1)

    def test_fallback_then_late_ready_publishes_once(self):
        self.join(defer_scene_snapshot=True)
        self.assertTrue(self.ns["sync_loaded_world_snapshot"]())
        self.assertFalse(self.ns["sync_loaded_world_snapshot"](force=True))
        self.assert_dynamic_count(1)

    def test_default_join_preserves_immediate_reconnect_snapshot(self):
        self.join()
        self.assert_dynamic_count(1)

    def test_explicit_scene_recovery_remains_available(self):
        self.ns["world_snapshot_pending"] = False
        self.ns["send_loaded_world_snapshot"]()
        self.assert_dynamic_count(1)

    def test_both_transport_paths_defer_public_but_not_private_scene(self):
        tree = ast.parse(SERVER.read_text())
        deferred = [
            keyword.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "join_world"
            for keyword in node.keywords
            if keyword.arg == "defer_scene_snapshot"
        ]
        self.assertEqual(len(deferred), 2)
        for expression in deferred:
            code = compile(ast.Expression(expression), str(SERVER), "eval")
            self.assertTrue(eval(code, {"character": {"map_id": 527}}))
            self.assertFalse(eval(code, {"character": {"map_id": 9}}))

    def test_stale_destination_cannot_receive_deferred_snapshot(self):
        self.join(defer_scene_snapshot=True)
        self.ns["character"]["map_id"] = 528
        self.assertFalse(self.ns["sync_loaded_world_snapshot"](force=True))
        self.assert_dynamic_count(0)


if __name__ == "__main__":
    unittest.main()
