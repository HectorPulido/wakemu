"""Exercise the dispatcher timer and native overlay boundaries without sockets."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

from test_static_map_sync_dispatch import _session_function, SERVER_SOURCE
from wakfu_server import environment_interactions
from wakfu_server.characters import heroes


def helpers(namespace):
    names = (
        "cancel_environment",
        "environment_actor_is_hero",
        "complete_environment_occupation",
        "publish_environment_scene",
    )
    factory = ast.parse(
        "def factory():\n    environment_ticket = initial_ticket\n    environment_seat = None\n    character = initial_character\n    environment_scene_identity = None\n    environment_scene_states = {}\n    last_environment_refresh = 0.0\n    def state():\n        return environment_ticket, character\n    return locals()\n"
    ).body[0]
    factory.body[-1:-1] = [deepcopy(_session_function(name)) for name in names]
    module = ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[]))
    exec(compile(module, str(SERVER_SOURCE), "exec"), namespace)
    return namespace["factory"]()


class EnvironmentDispatchTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.actor = dict(
            id=7,
            map_id=472,
            instance_id=0,
            x=0,
            y=0,
            z=8,
            current_hp=91,
            active_build=3,
        )
        self.ticket = dict(
            character_id=7, map_id=472, x=0, y=0, z=8, token="durable", due_at=self.now
        )
        self.sent, self.cancelled = [], []
        self.namespace = dict(
            initial_ticket=self.ticket,
            initial_character=self.actor,
            loaded=True,
            STORE=SimpleNamespace(now=lambda: self.now),
            account_id=4,
            generation=9,
            environment_blocked=lambda: False,
            fight=None,
            combat_session=None,
            spectator_session=None,
            connection=None,
            service="world",
            time=SimpleNamespace(monotonic=lambda: 2),
            struct=struct,
            send=lambda connection, service, *packet: self.sent.append(packet),
            record=lambda **row: None,
            world_static=SimpleNamespace(
                objects=lambda map_id: (
                    dict(id=10, x=1, y=1),
                    dict(id=20, x=1000, y=1000),
                )
            ),
        )
        self.scope = helpers(self.namespace)
        self.cancel = patch.object(
            environment_interactions,
            "cancel",
            side_effect=lambda *args: self.cancelled.append(args),
        )
        self.cancel.start()
        self.addCleanup(self.cancel.stop)

    def test_owned_roster_requires_explicit_identity(self):
        with patch.object(
            heroes,
            "ensure_company_party",
            return_value={"leader": {"id": 7}, "heroes": ({"id": 8},)},
        ):
            self.assertIs(self.scope["environment_actor_is_hero"](), False)
            self.actor["id"] = 8
            self.assertIs(self.scope["environment_actor_is_hero"](), True)
            self.actor["id"] = 9
            with self.assertRaises(ValueError):
                self.scope["environment_actor_is_hero"]()

    def test_timer_grants_once_without_overwriting_build_hp_or_location(self):
        result = dict(
            packets=[(12000, b"water")],
            character=dict(
                inventory_items=["water"],
                inventory_containers=["bag"],
                current_hp=1,
                active_build=99,
                x=400,
            ),
        )
        with patch.object(
            environment_interactions, "complete", return_value=result
        ) as complete, patch.object(
            heroes,
            "ensure_company_party",
            return_value={"leader": {"id": 7}, "heroes": ()},
        ):
            self.ticket["due_at"] = self.now + timedelta(seconds=1)
            self.scope["complete_environment_occupation"]()
            complete.assert_not_called()
            self.now += timedelta(seconds=2)
            self.scope["complete_environment_occupation"]()
            self.scope["complete_environment_occupation"]()
            complete.assert_called_once()
        self.assertEqual(self.sent, [(12000, b"water")])
        self.assertEqual(
            (self.actor["current_hp"], self.actor["active_build"], self.actor["x"]),
            (91, 3, 0),
        )
        self.assertEqual(self.actor["inventory_items"], ["water"])
        self.assertIsNone(self.scope["state"]()[0])

    def test_movement_and_blocked_actor_cancel_before_reward(self):
        for moved in (True, False):
            with self.subTest(moved=moved):
                self.actor["x"] = 1 if moved else 0
                self.namespace["environment_blocked"] = lambda: not moved
                scope = helpers(self.namespace)
                with patch.object(environment_interactions, "complete") as complete:
                    scope["complete_environment_occupation"]()
                    complete.assert_not_called()
                self.assertIsNone(scope["state"]()[0])
        self.assertTrue(all(call[3] == 7 for call in self.cancelled))

    def test_overlay_is_nearby_diffed_and_force_reapplied(self):
        nearby = (12344, struct.pack(">q", 10) + b"lit")
        far = (12344, struct.pack(">q", 20) + b"lit")
        with patch.object(
            environment_interactions, "snapshots", return_value=(nearby, far)
        ), patch("wakfu_server.environment_seats.snapshots", return_value=()), patch(
            "wakfu_server.environment_doors.snapshots", return_value=()
        ):
            self.scope["publish_environment_scene"](force=True)
            self.scope["publish_environment_scene"](force=True)
            self.scope["publish_environment_scene"]()
        self.assertEqual(self.sent, [nearby, nearby])
        self.namespace["loaded"] = False
        with patch.object(environment_interactions, "snapshots") as snapshots:
            self.scope["publish_environment_scene"](force=True)
            snapshots.assert_not_called()

    def test_overlay_combines_tuple_list_and_generator_snapshots(self):
        interaction = (12344, struct.pack(">q", 10) + b"light")
        seat = (12344, struct.pack(">q", 11) + b"seat")
        door = (12344, struct.pack(">q", 12) + b"door")
        far = (12344, struct.pack(">q", 20) + b"far")
        self.namespace["world_static"].objects = lambda map_id: (
            dict(id=10, x=1, y=1),
            dict(id=11, x=1, y=1),
            dict(id=12, x=1, y=1),
            dict(id=20, x=1000, y=1000),
        )
        with patch.object(
            environment_interactions, "snapshots", return_value=(interaction,)
        ), patch.object(
            importlib.import_module("wakfu_server.environment_seats"),
            "snapshots",
            return_value=[seat],
        ), patch.object(
            importlib.import_module("wakfu_server.environment_doors"),
            "snapshots",
            return_value=(packet for packet in (door, far)),
        ):
            self.scope["publish_environment_scene"](force=True)

        self.assertEqual(self.sent, [interaction, seat, door])

    def test_wire_and_logout_cancellation_are_explicit(self):
        source = SERVER_SOURCE.read_text()
        self.assertIn(
            'logout_barrier("environment_occupation", lambda: cancel_environment(publish=False))',
            source,
        )
        session = ast.parse(source)
        gate = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and "environment_ticket is not None or environment_seat is not None"
            in ast.unparse(node.test)
            and "opcode in" in ast.unparse(node.test)
        )
        values = {
            node.value for node in ast.walk(gate.test) if isinstance(node, ast.Constant)
        }
        self.assertTrue({13331, 13130, 12006, 12054, 12247}.issubset(values))
        generic = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 12870 and character['map_id'] != 9"
        )
        text = ast.unparse(generic)
        self.assertLess(
            text.index("environment_interactions.definition"),
            text.index("world_static.interaction"),
        )
        self.assertIn("is_hero=environment_actor_is_hero()", text)
        self.assertNotIn("WORLD.emit_location", text)
        self.assertIn("publish_environment_scene(force=True)", text)
