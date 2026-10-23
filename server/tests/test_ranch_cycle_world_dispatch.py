"""Focused World gates for Ranch reward pickup and idle cycle settlement."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import wakfu_server
from wakfu_server import haven_ranch_building_knowledge
from psycopg import DatabaseError
from psycopg_pool import PoolTimeout


WORLD_SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


class RanchCycleWorldDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(WORLD_SOURCE.read_text())
        cls.tick_function = next(
            node
            for node in ast.walk(cls.tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "deliver_ranch_cycle_rewards"
        )
        cls.pickup_branch = next(
            node
            for node in ast.walk(cls.tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "loaded and opcode in (12068, 12320)"
        )

    def _tick(
        self,
        *,
        loaded=True,
        owner=True,
        combat=None,
        pending_return=None,
        error=None,
        packets=None
    ):
        parent = SimpleNamespace(is_owner=owner)
        ranch_session = (
            SimpleNamespace(parent=parent, biome_id=1) if owner is not None else None
        )
        character = {"id": 41, "map_id": 1440, "instance_id": 17}
        sent, emitted, events = [], [], []
        tick = Mock(return_value=packets or [], side_effect=error)
        reward_module = SimpleNamespace(tick=tick)
        enclosing = ast.FunctionDef(
            name="build",
            args=ast.arguments(
                posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
            ),
            body=[
                ast.Assign(
                    targets=[ast.Name(id="last_ranch_cycle_tick", ctx=ast.Store())],
                    value=ast.Constant(value=0),
                ),
                deepcopy(self.tick_function),
                ast.Return(
                    value=ast.Name(id="deliver_ranch_cycle_rewards", ctx=ast.Load())
                ),
            ],
            decorator_list=[],
        )
        module = ast.fix_missing_locations(
            ast.Module(body=[enclosing], type_ignores=[])
        )
        namespace = {
            "loaded": loaded,
            "ranch_session": ranch_session,
            "fight": object() if combat == "fight" else None,
            "combat_session": object() if combat == "combat" else None,
            "spectator_session": object() if combat == "spectator" else None,
            "hero_switch_pending": pending_return,
            "time": SimpleNamespace(monotonic=lambda: 1000.0),
            "STORE": object(),
            "account_id": 7,
            "generation": "lease",
            "character": character,
            "WORLD": SimpleNamespace(emit_location=lambda *args: emitted.append(args)),
            "record": lambda **event: events.append(event),
            "send": lambda *args: sent.append(args[2:]),
            "connection": object(),
            "service": "world",
            "DatabaseError": DatabaseError,
            "PoolTimeout": PoolTimeout,
        }
        exec(compile(module, str(WORLD_SOURCE), "exec"), namespace)
        callback = namespace["build"]()
        with patch.object(
            wakfu_server, "ranch_cycle_rewards", reward_module, create=True
        ), patch.object(
            haven_ranch_building_knowledge,
            "scene_packet",
            return_value=(13864, b"host-scene"),
        ):
            callback()
        return SimpleNamespace(
            tick=tick, sent=sent, emitted=emitted, events=events, ns=namespace
        )

    def test_idle_owner_cycle_tick_sends_packets_and_defers_failures(self):
        result = self._tick(packets=[(13964, b"reward")])
        result.tick.assert_called_once_with(
            result.ns["STORE"],
            7,
            "lease",
            result.ns["character"],
            session=result.ns["ranch_session"],
        )
        self.assertEqual(result.sent, [(13964, b"reward")])
        self.assertEqual(result.emitted, [(1440, 17, 13864, b"host-scene")])

        deferred = self._tick(error=ValueError("stale owner session"))
        self.assertFalse(deferred.sent)
        self.assertEqual(deferred.events[0]["event"], "haven_ranch_cycle_deferred")
        self.assertEqual(deferred.events[0]["reason"], "stale owner session")

    def test_cycle_tick_skips_visitors_combat_pending_return_and_unloaded_world(self):
        cases = (
            {"loaded": False},
            {"owner": False},
            {"owner": None},
            {"combat": "fight"},
            {"combat": "combat"},
            {"combat": "spectator"},
            {"pending_return": object()},
        )
        for options in cases:
            with self.subTest(options=options):
                result = self._tick(**options)
                result.tick.assert_not_called()

    def test_pickup_world_route_uses_real_retrieval_and_host_scene_publication(self):
        branch = deepcopy(self.pickup_branch)
        function = ast.FunctionDef(
            name="route",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="character")],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=[ast.If(test=branch.test, body=branch.body, orelse=[])],
            decorator_list=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        main = {"id": 41, "map_id": 1440, "instance_id": 17}
        hero = {"id": 42, "map_id": 1440, "instance_id": 17}
        outcome = dict(
            recipient_character_id=42,
            character=hero,
            applied=True,
            reward_uids=[81],
            packets=[(13964, b"ledger")],
        )
        retrieve = Mock(return_value=outcome)
        sent, emitted, events = [], [], []
        world = SimpleNamespace(emit_location=lambda *args: emitted.append(args))
        namespace = {
            "loaded": True,
            "opcode": 12068,
            "body": b"request",
            "fight": None,
            "combat_session": None,
            "spectator_session": None,
            "cancel_crafting": Mock(),
            "STORE": object(),
            "account_id": 7,
            "generation": "lease",
            "character": main,
            "ranch_session": SimpleNamespace(biome_id=1),
            "refresh_owned_character": Mock(return_value={"id": 43}),
            "send": lambda _connection, _service, *packet: sent.append(packet),
            "connection": object(),
            "service": "world",
            "WORLD": world,
            "record": lambda **event: events.append(event),
            "DatabaseError": DatabaseError,
            "PoolTimeout": PoolTimeout,
        }
        scene_packet = Mock(return_value=(13864, b"host-scene"))
        with patch.object(
            wakfu_server,
            "ranch_reward_retrieval",
            SimpleNamespace(retrieve=retrieve),
            create=True,
        ), patch.object(haven_ranch_building_knowledge, "scene_packet", scene_packet):
            exec(compile(module, str(WORLD_SOURCE), "exec"), namespace)
            namespace["route"](main)

        retrieve.assert_called_once_with(
            namespace["STORE"],
            7,
            "lease",
            main,
            12068,
            b"request",
            session=namespace["ranch_session"],
        )
        self.assertEqual(sent, [(13964, b"ledger")])
        self.assertEqual(emitted, [(1440, 17, 13864, b"host-scene")])
        # Delivering to an active hero must not switch the main actor snapshot.
        namespace["refresh_owned_character"].assert_not_called()
        scene_packet.assert_called_once_with(namespace["STORE"], 7, biome_id=1)
        self.assertEqual(events[-1]["recipient_character_id"], 42)

    def test_pickup_world_route_rejects_combat_before_domain_call(self):
        branch = deepcopy(self.pickup_branch)
        function = ast.FunctionDef(
            name="route",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="character")],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=[ast.If(test=branch.test, body=branch.body, orelse=[])],
            decorator_list=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        retrieve = Mock()
        sent, events = [], []
        namespace = {
            "loaded": True,
            "opcode": 12320,
            "body": b"request",
            "fight": object(),
            "combat_session": None,
            "spectator_session": None,
            "cancel_crafting": Mock(),
            "STORE": object(),
            "account_id": 7,
            "generation": "lease",
            "character": {"id": 41, "map_id": 1440, "instance_id": 17},
            "ranch_session": SimpleNamespace(biome_id=1),
            "send": lambda _connection, _service, *packet: sent.append(packet),
            "connection": object(),
            "service": "world",
            "WORLD": SimpleNamespace(),
            "record": lambda **event: events.append(event),
            "DatabaseError": DatabaseError,
            "PoolTimeout": PoolTimeout,
        }
        with patch.object(
            wakfu_server,
            "ranch_reward_retrieval",
            SimpleNamespace(retrieve=retrieve),
            create=True,
        ):
            exec(compile(module, str(WORLD_SOURCE), "exec"), namespace)
            namespace["route"](namespace["character"])
        retrieve.assert_not_called()
        namespace["cancel_crafting"].assert_not_called()
        self.assertEqual(len(sent), 1)
        self.assertEqual(events[-1]["event"], "haven_ranch_rewards_rejected")


if __name__ == "__main__":
    unittest.main()
