"""Execute the extracted native hero switch dispatcher branches in isolation."""
import ast
import struct
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from wakfu_server import hero_wire


def dispatcher_branches():
    tree = ast.parse(
        Path(__file__).resolve().parents[1].joinpath("local_game_server.py").read_text()
    )
    return {
        opcode: next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and f"opcode == {opcode}" in ast.unparse(node.test)
        )
        for opcode in (12006, 12054)
    }


class HeroSwitchDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.branches = dispatcher_branches()

    def run_branch(
        self,
        opcode,
        *,
        character_id=42,
        pending=None,
        session_valid=True,
        requested_id=42,
        flush_error=None,
    ):
        events = []
        character = {
            "id": character_id,
            "account_id": 7,
            "level": 60,
            "x": 4,
            "y": 5,
            "z": 0,
        }

        class Positions:
            @contextmanager
            def account_barrier(self, _account_id):
                events.append(("barrier", "begin"))
                yield
                events.append(("barrier", "end"))

            def attach(self, account_id, generation, attached):
                events.append(("attach", account_id, generation, attached["id"]))

        class World:
            def leave(self, identity, generation):
                events.append(("leave", identity, generation))

        class Store:
            @staticmethod
            def current_character_session(account_id, generation, identity):
                events.append(("session", account_id, generation, identity))
                return session_valid

        class Movement:
            def __init__(self, position):
                events.append(("movement", position))

        wire_module = types.SimpleNamespace(
            fixture=lambda opcode: (
                events.append(("fixture", opcode)) or b"native-fixture"
            ),
            adapt=lambda opcode, template, owner, entity: (
                events.append(("adapt", opcode, template, owner, entity["id"]))
                or b"guild-refresh"
            ),
        )

        def flush_positions(**kwargs):
            events.append(("flush", kwargs))
            if flush_error is not None:
                raise flush_error

        namespace = {
            "opcode": opcode,
            "loaded": True,
            "body": struct.pack(">q", requested_id),
            "hero_switch_pending": pending,
            "character": character,
            "account_id": 7,
            "generation": "lease",
            "connection": object(),
            "service": "world",
            "fight": None,
            "combat_session": None,
            "ranch_session": None,
            "bag_session": None,
            "chest_opening": None,
            "npc_dialogue_session": None,
            "active_private_session": lambda: None,
            "PLANTINGS": types.SimpleNamespace(cancel=lambda *_args: None),
            "HARVESTS": types.SimpleNamespace(cancel=lambda *_args, **_kwargs: None),
            "cancel_flora": lambda: None,
            "STORE": Store(),
            "POSITIONS": Positions(),
            "WORLD": World(),
            "Movement": Movement,
            "OWNED_HERO_TEMPLATE": b"template",
            "wire": wire_module,
            "fixture": wire_module.fixture,
            "cancel_crafting": lambda: events.append(("cancel_crafting",)),
            "flush_positions": flush_positions,
            "send": lambda _connection, service, *packet: events.append(
                ("send", service, packet)
            ),
            "record": lambda **values: events.append(("record", values)),
            "join_world": lambda *args, **kwargs: events.append(
                ("join_world", args, kwargs)
            ),
            "rich_inventory_packet": lambda _character: (13220, b"inventory"),
            "publish_custom_task_cards": lambda: events.append(("publish_tasks",)),
            "deliver_custom_task_rewards": lambda: events.append(
                ("deliver_task_rewards",)
            ),
        }
        synchronization_module = types.ModuleType("wakfu_server.inventory_move")
        synchronization_module.synchronization = lambda _character: (13221, b"sync")
        feedback_module = types.ModuleType("wakfu_server.ecology_feedback")
        feedback_module.information = lambda _message: (674, b"info")
        loop = ast.For(
            target=ast.Name(id="_once", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(value=0)], ctx=ast.Load()),
            body=[self.branches[opcode]],
            orelse=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))
        patches = patch.dict(
            sys.modules,
            {
                "wakfu_server.inventory_move": synchronization_module,
                "wakfu_server.ecology_feedback": feedback_module,
            },
        )
        with patches, patch.object(
            hero_wire, "refresh", return_value=(13046, b"refresh")
        ), patch.object(hero_wire, "statistics", return_value=(13046, b"stats")):
            if opcode == 12006:
                from wakfu_server import heroes

                namespace["STORE"] = object()
                switched_leader = {
                    "id": requested_id,
                    "x": 9,
                    "y": 8,
                    "z": 0,
                    "map_id": 9,
                    "instance_id": 0,
                    "level": 60,
                    "breed": 1,
                    "account_id": 7,
                }
                namespace["_switched_leader"] = switched_leader
                with patch.object(
                    heroes,
                    "switch_main",
                    return_value={"leader": switched_leader},
                ) as switch_main:
                    exec(compile(module, "local_game_server.py", "exec"), namespace)
                    namespace["_switch_main"] = switch_main
            else:
                exec(compile(module, "local_game_server.py", "exec"), namespace)
        return namespace, events

    def test_request_hands_off_master_before_refreshing_private_components(self):
        namespace, events = self.run_branch(12006, requested_id=84)
        packets = [event[2] for event in events if event[0] == "send"]
        self.assertEqual(
            [
                (13440, struct.pack(">Bq", 0, 84)),
            ],
            packets,
        )
        self.assertEqual(84, namespace["hero_switch_pending"])
        self.assertFalse(any(event[0] == "join_world" for event in events))

    def test_matching_completion_joins_without_hydrating_again_then_syncs_once(self):
        namespace, events = self.run_branch(
            12054, character_id=84, pending=84, requested_id=84
        )
        self.assertIsNone(namespace["hero_switch_pending"])
        join = next(event for event in events if event[0] == "join_world")
        self.assertEqual({"hydrate_heroes": False}, join[2])
        sent = [event[2][0] for event in events if event[0] == "send"]
        self.assertEqual([13046, 13046, 15548, 13220, 13221], sent)
        self.assertEqual(
            [event[2] for event in events if event[0] == "send"][:2],
            [(13046, b"refresh"), (13046, b"stats")],
        )
        first_refresh_index = next(
            index
            for index, event in enumerate(events)
            if event[0] == "send" and event[2][0] == 13046
        )
        lease_index = next(
            index for index, event in enumerate(events) if event[0] == "session"
        )
        self.assertLess(lease_index, first_refresh_index)
        guild_refresh_index = next(
            index
            for index, event in enumerate(events)
            if event[0] == "send" and event[2][0] == 15548
        )
        self.assertLess(guild_refresh_index, events.index(join))
        self.assertIn(("adapt", 15548, b"native-fixture", 7, 84), events)

    def test_wrong_target_stale_lease_and_unexpected_completion_do_not_join(self):
        cases = ((84, 85, True), (84, 84, False), (None, 84, True), (None, 85, True))
        for pending, requested, valid_lease in cases:
            with self.subTest(
                pending=pending, requested=requested, valid_lease=valid_lease
            ):
                _, events = self.run_branch(
                    12054,
                    pending=pending,
                    requested_id=requested,
                    session_valid=valid_lease,
                )
                self.assertFalse(any(event[0] == "join_world" for event in events))
                self.assertFalse(
                    any(
                        event[0] == "send"
                        and event[2][0] in (13046, 15548, 13220, 13221)
                        for event in events
                    )
                )

    def test_duplicate_completion_does_not_replace_owned_components(self):
        namespace, events = self.run_branch(
            12054, character_id=84, pending=None, requested_id=84
        )
        self.assertIsNone(namespace["hero_switch_pending"])
        self.assertFalse(any(event[0] in ("send", "join_world") for event in events))

    def test_position_contention_rejects_before_switching_without_losing_main(self):
        from wakfu_server.position_buffer import PositionOwnerBusy

        namespace, events = self.run_branch(
            12006,
            requested_id=84,
            flush_error=PositionOwnerBusy("Position owner is busy; retry checkpoint"),
        )
        namespace["_switch_main"].assert_not_called()
        self.assertEqual(namespace["character"]["id"], 42)
        self.assertIsNone(namespace["hero_switch_pending"])
        self.assertFalse(
            any(event[0] in ("leave", "join_world", "attach") for event in events)
        )
        packets = [event[2] for event in events if event[0] == "send"]
        self.assertEqual(packets, [(13440, struct.pack(">Bq", 6, 84)), (674, b"info")])
        self.assertTrue(
            any(
                event[0] == "record" and event[1]["event"] == "hero_switch_rejected"
                for event in events
            )
        )


if __name__ == "__main__":
    unittest.main()
