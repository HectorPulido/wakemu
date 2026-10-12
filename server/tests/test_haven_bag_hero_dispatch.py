"""Execute the production hero-switch dispatcher branch for an active bag owner."""
import ast
import struct
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.characters import heroes, hero_wire


class HavenBagHeroDispatcherTests(unittest.TestCase):
    def test_owned_switch_rebinds_interior_after_exterior_position_attach(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "opcode == 12006 and loaded" in ast.unparse(node.test)
        )
        events = []
        original = dict(
            id=41,
            account_id=7,
            map_id=1134,
            instance_id=0,
            x=7,
            y=14,
            z=-1,
            name="Original",
            level=10,
            haven_bag={"owner_id": 3, "rooms": ["stored"]},
        )
        session = HavenBagSession(original)
        previous = session.move(session.inside, dict(x=-4, y=2, z=0))
        previous["haven_bag"] = {"owner_id": 3, "rooms": ["active-layout"]}
        selected = dict(
            original,
            id=42,
            x=20,
            y=30,
            z=1,
            level=25,
            builds={"active": 1},
        )
        roster = {"leader": selected}

        class Positions:
            @contextmanager
            def account_barrier(self, account_id):
                events.append(("barrier", account_id))
                yield

            def attach(self, account_id, generation, character):
                events.append(("attach", account_id, generation, dict(character)))

        class World:
            def leave(self, identity, generation):
                events.append(("leave", identity, generation))

        class Movement:
            def __init__(self, position):
                events.append(("movement", position))

        feedback = types.ModuleType("wakfu_server.ecology_feedback")
        feedback.information = lambda text: (674, text.encode())
        namespace = {
            "opcode": 12006,
            "loaded": True,
            "body": struct.pack(">q", selected["id"]),
            "hero_switch_pending": None,
            "character": previous,
            "account_id": 7,
            "generation": "session-1",
            "connection": object(),
            "service": "world",
            "fight": None,
            "combat_session": None,
            "ranch_session": None,
            "bag_session": session,
            "chest_opening": object(),
            "active_private_session": lambda: session,
            "POSITIONS": Positions(),
            "WORLD": World(),
            "STORE": object(),
            "PLANTINGS": types.SimpleNamespace(
                cancel=lambda *args: events.append(("cancel_planting", args))
            ),
            "HARVESTS": types.SimpleNamespace(
                cancel=lambda *args, **kwargs: events.append(
                    ("cancel_harvest", args, kwargs)
                )
            ),
            "cancel_flora": lambda: events.append(("cancel_flora",)),
            "cancel_crafting": lambda: events.append(("cancel_crafting",)),
            "flush_positions": lambda **kwargs: events.append(("flush", kwargs)),
            "Movement": Movement,
            "OWNED_HERO_TEMPLATE": b"native-template",
            "publish_heroes": lambda current: events.append(("publish", current)),
            "send": lambda _connection, service, *packet: events.append(
                ("send", service, packet)
            ),
            "record": lambda **values: events.append(("record", values)),
        }
        module = ast.fix_missing_locations(
            ast.Module(
                body=[
                    ast.For(
                        target=ast.Name(id="_once", ctx=ast.Store()),
                        iter=ast.Tuple(elts=[ast.Constant(value=0)], ctx=ast.Load()),
                        body=[branch],
                        orelse=[],
                    )
                ],
                type_ignores=[],
            )
        )
        with patch.dict(
            sys.modules, {"wakfu_server.ecology_feedback": feedback}
        ), patch.object(
            heroes, "switch_main", return_value=roster
        ) as switch_main, patch.object(
            hero_wire, "refresh", return_value=(13046, b"refresh")
        ), patch.object(
            hero_wire, "statistics", return_value=(13047, b"stats")
        ), patch.object(
            hero_wire, "switched_result", return_value=(13440, b"switched")
        ):
            exec(compile(module, str(source), "exec"), namespace)

        attach = next(event for event in events if event[0] == "attach")
        self.assertEqual(1134, attach[3]["map_id"])
        self.assertEqual(20, attach[3]["x"])
        self.assertEqual(42, namespace["character"]["id"])
        self.assertEqual(
            (9, 3, -4, 2, 0),
            tuple(
                namespace["character"][key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            ),
        )
        self.assertEqual(
            {"owner_id": 3, "rooms": ["active-layout"]},
            namespace["character"]["haven_bag"],
        )
        self.assertEqual(42, namespace["hero_switch_pending"])
        self.assertIsNone(namespace["chest_opening"])
        switch_main.assert_called_once_with(namespace["STORE"], 7, "session-1", 41, 42)
        from wakfu_server.haven_chest_wire import close_packet

        close_index = next(
            i
            for i, event in enumerate(events)
            if event[0] == "send" and event[2] == close_packet(41)
        )
        leave_index = next(i for i, event in enumerate(events) if event[0] == "leave")
        refresh_index = next(
            i
            for i, event in enumerate(events)
            if event[0] == "send" and event[2] == (13046, b"refresh")
        )
        self.assertEqual(
            (12088, struct.pack(">BhqI", 2, 31, 41, 0)), events[close_index][2]
        )
        self.assertEqual(15, len(events[close_index][2][1]))
        self.assertLess(close_index, leave_index)
        self.assertLess(close_index, refresh_index)
        self.assertLess(events.index(attach), refresh_index)


if __name__ == "__main__":
    unittest.main()
