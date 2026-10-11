"""Execute actual dispatcher branches against the shared tactical domain."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

import test_combat_tactical_markers as tactical_fixtures
from wakfu_server.combat import combat_tactical_markers as markers
from wakfu_server.combat_shared import Batch

SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


def function(name):
    return deepcopy(
        next(
            node
            for node in ast.walk(ast.parse(SERVER.read_text()))
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
    )


class TacticalMarkerDispatchTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tactical_fixtures.TacticalMarkersTests()
        self.fixture.setUp()
        self.fx = self.fixture
        self.events, self.calls = [], []
        self.scope = dict(
            loaded=True,
            combat_session=self.fx.sessions[1],
            fight=self.fx.fight,
            opcode=markers.PING,
            body=struct.pack(">iih", 4, 0, 0),
            character={"id": 10},
            COMBAT_SESSIONS=SimpleNamespace(registry=self.fx.registry),
            refresh_shared_combat=lambda: self.calls.append("refresh"),
            checkpoint_fight=lambda: self.calls.append("checkpoint"),
            drain_shared_combat=lambda: self.calls.append("drain"),
            record=lambda **event: self.events.append(event),
        )
        branch = next(
            node
            for node in ast.walk(ast.parse(SERVER.read_text()))
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode in (12543, 12519, 12597) and loaded"
        )
        self.branch = ast.fix_missing_locations(
            ast.Module(body=branch.body, type_ignores=[])
        )

    def dispatch(self):
        exec(compile(self.branch, str(SERVER), "exec"), self.scope)

    def test_native_requests_reach_owned_hero_and_team_only_outboxes(self):
        self.fx.fight.phase = "active"
        self.fx.fight.order = [11, 30, 10, 20]
        self.dispatch()
        self.assertEqual(self.calls, ["refresh", "checkpoint", "drain"])
        packets = self.fx.registry.drain(77, self.fx.sessions[2])[0].packets
        self.assertEqual(packets, ((13788, struct.pack(">iiihq", 77, 4, 0, 0, 11)),))
        self.assertEqual(self.fx.registry.drain(77, self.fx.sessions[3]), [])
        self.dispatch()
        self.assertEqual(self.calls.count("drain"), 1)
        self.assertFalse(self.events[-1]["accepted"])

    def test_other_owners_turn_uses_main_and_unowned_sessions_are_rejected(self):
        self.fx.fight.phase = "active"
        self.fx.fight.order = [30, 10, 20, 11]
        self.dispatch()
        self.assertEqual(self.events[-1]["actor_id"], 10)
        self.scope["combat_session"] = None
        self.dispatch()
        self.assertEqual(self.events[-1]["event"], "combat_tactical_signal_rejected")
        self.assertEqual(self.calls.count("drain"), 1)

    def test_malformed_request_never_checkpoints_or_drains(self):
        self.scope["body"] = b"bad"
        self.dispatch()
        self.assertEqual(self.calls, ["refresh"])
        self.assertEqual(self.events[-1]["event"], "combat_tactical_signal_rejected")

    def test_bootstrap_replays_authenticated_team_icons_after_constructor_only(self):
        self.fx.action(icon=7)
        for queue in self.fx.shared.outboxes.values():
            queue.clear()
        owner = self.fx.sessions[2]
        pending = [Batch(10, ((12847, b"native-constructor"),))]
        sent, observer = [], []
        adapter = SimpleNamespace(
            registry=self.fx.registry,
            dispatch_connected=lambda fight_id, deliver: deliver(owner, pending),
        )
        scope = dict(
            PROFILER=SimpleNamespace(profile=lambda name: lambda fn: fn),
            combat_session=self.fx.sessions[1],
            fight=self.fx.fight,
            COMBAT_SESSIONS=adapter,
            publish_external_marker=lambda shared: None,
            publish_spectator_state=lambda shared, packets: observer.append(packets),
            WORLD=SimpleNamespace(
                send_batch_to=lambda actor, generation, packets: sent.append(
                    (actor, packets)
                )
            ),
            send_batch=lambda *args: self.fail(
                "Other owner must use its authenticated socket"
            ),
            connection=None,
            service="world",
        )
        module = ast.fix_missing_locations(
            ast.Module(body=[function("drain_shared_combat")], type_ignores=[])
        )
        exec(compile(module, str(SERVER), "exec"), scope)
        scope["drain_shared_combat"]()
        self.assertEqual(sent[0][0], 20)
        self.assertEqual(sent[0][1][0], (12847, b"native-constructor"))
        self.assertEqual(sent[0][1][1:], markers.snapshots(self.fx.registry, owner, 77))
        self.assertEqual(observer, [()])
        pending[:] = [Batch(11, ((13788, b"private-ping"),))]
        with patch.object(markers, "snapshots") as snapshots:
            scope["drain_shared_combat"]()
            snapshots.assert_not_called()
        self.assertEqual(observer[-1], ())
