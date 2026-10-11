"""Execute the Ranch branches copied directly from the production dispatcher AST."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
import time
import unittest
from unittest.mock import patch

from wakfu_server.haven_bag import HavenBagSession


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _session_function():
    tree = ast.parse(SERVER_SOURCE.read_text(encoding="utf-8"))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "session"
    )


def _branch(predicate):
    return next(
        node
        for node in ast.walk(_session_function())
        if isinstance(node, ast.If) and predicate(ast.unparse(node.test))
    )


def _execute_branch(branch, *, globals_, locals_):
    """Compile the actual selected branch with explicit dispatcher locals."""
    branch = deepcopy(branch)
    # A packet dispatcher is one long `if/elif` chain. The test executes only
    # the selected production branch, so omit its following `elif` siblings.
    branch.orelse = []
    args = [ast.arg(arg=name) for name in locals_]
    function = ast.FunctionDef(
        name="dispatch_branch",
        args=ast.arguments(
            posonlyargs=[],
            args=args,
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        ),
        body=[
            ast.fix_missing_locations(branch),
            ast.Return(
                value=ast.Dict(
                    keys=[ast.Constant(value=name) for name in locals_],
                    values=[ast.Name(id=name, ctx=ast.Load()) for name in locals_],
                )
            ),
        ],
        decorator_list=[],
    )
    ast.fix_missing_locations(function)
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(SERVER_SOURCE), "exec"), globals_)
    return globals_["dispatch_branch"](**locals_)


class RanchDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.outside = {
            "id": 10,
            "account_id": 2,
            "map_id": 1134,
            "instance_id": 0,
            "x": -9,
            "y": -4,
            "z": -1,
            "name": "Owner",
            "hp": 31,
            "haven_bag": {"appearance_id": 408, "rooms": [], "furniture": []},
        }
        self.bag = HavenBagSession(self.outside)
        self.actor = self.bag.move(self.bag.inside, {"x": -8, "y": 5, "z": 4})
        self.sent = []
        self.events = []
        self.context = {"lease_valid": True, "account_id": 2, "generation": "lease"}
        self.globals = {
            "time": time,
            "struct": struct,
            "STORE": type(
                "Store",
                (),
                {
                    "current_character_session": staticmethod(
                        lambda account, generation, actor_id: self.context[
                            "lease_valid"
                        ]
                        and account == self.context["account_id"]
                        and generation == self.context["generation"]
                        and actor_id == 10
                    )
                },
            )(),
            "connection": object(),
            "service": "world",
            "send": lambda connection, service, opcode, body: self.sent.append(
                (opcode, body)
            ),
            "fixture": lambda opcode: b"native-template",
            "Movement": lambda position: ("movement", dict(position)),
            "map_geometry": lambda map_id: {
                "map_id": map_id,
                "cells": [[-8, 5, 4], [3, 3, 0]],
            },
            "cancel_private_scene_activity": lambda: self.events.append("cancel"),
            "join_world": lambda generation, connection, character, **kwargs: self.events.append(
                (
                    "join",
                    character["map_id"],
                    character["instance_id"],
                    kwargs.get("hydrate_heroes"),
                )
            ),
            "mark_static_sync_pending": lambda: self.events.append("static-sync"),
            "record": lambda **event: self.events.append(("record", event["event"])),
            "validate_ranch_lease": lambda: self._validate_lease(),
            "validate_ranch_entitlement": lambda: self._validate_entitlement(),
        }

    def _validate_lease(self):
        if not self.context["lease_valid"]:
            raise ValueError("Expired ranch actor lease")

    def _validate_entitlement(self):
        if not self.context.get("entitled", True):
            raise ValueError("Missing current Ranch entitlement")

    def _dispatch(
        self,
        opcode,
        body,
        *,
        character=None,
        ranch_session=None,
        bag_session=None,
        fight=None,
        spectator_session=None
    ):
        branch = _branch(
            lambda text: text.startswith("loaded and (opcode in (12380, 13982)")
        )
        locals_ = {
            "loaded": True,
            "opcode": opcode,
            "body": body,
            "character": dict(character or self.actor),
            "ranch_session": ranch_session,
            "bag_session": bag_session if bag_session is not None else self.bag,
            "fight": fight,
            "spectator_session": spectator_session,
            "generation": self.context["generation"],
            "movement_state": None,
            "packets": (),
        }
        return _execute_branch(branch, globals_=self.globals, locals_=locals_)

    def test_actual_dispatch_enters_then_returns_to_parent_bag(self):
        from wakfu_server import haven_bag

        body = struct.pack(">qHH", 36028, 35, 0)
        with patch(
            "wakfu_server.haven_ranch_authority.world_static.objects",
            return_value=[
                {
                    "id": 36028,
                    "type": "RanchEntrance",
                    "map_id": 9,
                    "x": -9,
                    "y": 5,
                    "z": 4,
                }
            ],
        ), patch(
            "wakfu_server.combat_terrain.map_geometry",
            return_value={
                "map_id": 9,
                "cells": [[-8, 5, 4], [3, 3, 0]],
            },
        ), patch.object(
            haven_bag,
            "map_transition",
            side_effect=lambda _template, actor, map_id: struct.pack(
                ">qi", actor["id"], map_id
            ),
        ), patch(
            "wakfu_server.haven_bag_furniture_world.packets", return_value=[]
        ):
            state = self._dispatch(12870, body)
            character, ranch, bag, movement = (
                state["character"],
                state["ranch_session"],
                state["bag_session"],
                state["movement_state"],
            )

            self.assertEqual(character["map_id"], 1440)
            self.assertIsNotNone(ranch)
            self.assertIs(bag, self.bag)
            self.assertEqual(
                [opcode for opcode, _ in self.sent], [13256, 13864, 13974, 12318]
            )
            self.assertEqual(
                self.events[:2],
                ["cancel", ("join", 1440, self.bag.bag_instance_id, False)],
            )
            self.assertEqual(self.events[-1], "static-sync")
            self.assertEqual(movement[1], {"x": 28, "y": 6, "z": 4})

            self.sent.clear()
            self.events.clear()
            self.context["entitled"] = False
            state = self._dispatch(
                13982,
                b"\x00",
                character=character,
                ranch_session=ranch,
                bag_session=bag,
            )
            returned, closed, bag, movement = (
                state["character"],
                state["ranch_session"],
                state["bag_session"],
                state["movement_state"],
            )

        self.assertIsNone(closed)
        self.assertEqual(
            (returned["map_id"], returned["instance_id"], returned["x"], returned["y"]),
            (9, self.bag.bag_instance_id, -8, 5),
        )
        self.assertEqual(
            [opcode for opcode, _ in self.sent], [13256, 13974, 12318, 12187]
        )
        self.assertNotIn(13864, [opcode for opcode, _ in self.sent])
        self.assertEqual(
            self.events[:2], ["cancel", ("join", 9, self.bag.bag_instance_id, True)]
        )
        self.assertEqual(self.events[-1], "static-sync")
        self.assertEqual(movement[1], {"x": -8, "y": 5, "z": 4})

    def test_stale_lease_and_guest_are_rejected_before_scene_or_position_changes(self):
        from wakfu_server import haven_bag

        body = struct.pack(">qHH", 36028, 35, 0)
        source = {
            "id": 36028,
            "type": "RanchEntrance",
            "map_id": 9,
            "x": -9,
            "y": 5,
            "z": 4,
        }
        with patch(
            "wakfu_server.haven_ranch_authority.world_static.objects",
            return_value=[source],
        ), patch.object(
            haven_bag, "map_transition", side_effect=AssertionError("must not publish")
        ):
            self.context["lease_valid"] = False
            original = dict(self.actor)
            state = self._dispatch(12870, body)
            character, ranch = state["character"], state["ranch_session"]
            self.assertEqual(character, original)
            self.assertIsNone(ranch)
            self.assertNotIn("cancel", self.events)
            self.assertFalse(
                any(
                    isinstance(event, tuple) and event[0] == "join"
                    for event in self.events
                )
            )

            self.sent.clear()
            self.events.clear()
            self.context["lease_valid"] = True
            guest = HavenBagSession(
                self.outside, owner={**self.outside, "id": 20, "account_id": 3}
            )
            guest_actor = guest.move(guest.inside, {"x": -8, "y": 5, "z": 4})
            state = self._dispatch(
                12870, body, character=guest_actor, bag_session=guest
            )
            character, ranch = state["character"], state["ranch_session"]

        self.assertEqual(character, guest_actor)
        self.assertIsNone(ranch)
        self.assertNotIn("cancel", self.events)
        self.assertFalse(
            any(
                isinstance(event, tuple) and event[0] == "join" for event in self.events
            )
        )

    def test_missing_current_entitlement_rejects_actual_entry_and_switch(self):
        from wakfu_server.haven_ranch import RanchSession

        self.context["entitled"] = False
        source = dict(id=36028, type="RanchEntrance", map_id=9, x=-9, y=5, z=4)
        with patch(
            "wakfu_server.haven_ranch_authority.world_static.objects",
            return_value=[source],
        ):
            state = self._dispatch(12870, struct.pack(">qHH", 36028, 35, 0))
        self.assertEqual(state["character"], self.actor)
        self.assertIsNone(state["ranch_session"])
        self.assertNotIn("cancel", self.events)
        self.assertFalse(
            any(opcode in (13256, 13864, 13974) for opcode, _ in self.sent)
        )
        child = RanchSession(
            self.bag,
            self.actor,
            dict(biome_id=1, map_id=1440, x=28, y=6, z=4),
            lease=1,
            now_ms=1000,
        )
        self.sent.clear()
        self.events.clear()
        state = self._dispatch(
            12380, struct.pack(">i", 1), character=child.inside, ranch_session=child
        )
        self.assertEqual(state["character"], child.inside)
        self.assertIs(state["ranch_session"], child)
        self.assertNotIn("cancel", self.events)
        self.assertFalse(
            any(opcode in (13256, 13864, 13974) for opcode, _ in self.sent)
        )

    def test_actual_entitlement_supplier_uses_current_actor_and_generation(self):
        function = next(
            node
            for node in ast.walk(_session_function())
            if isinstance(node, ast.FunctionDef)
            and node.name == "validate_ranch_entitlement"
        )
        module = ast.Module(body=[deepcopy(function)], type_ignores=[])
        context = dict(
            STORE=object(),
            account_id=2,
            generation="new-generation",
            character=dict(self.actor),
        )
        with patch(
            "wakfu_server.haven_ranch_authority.require_owned_entitlement"
        ) as check:
            exec(
                compile(ast.fix_missing_locations(module), str(SERVER_SOURCE), "exec"),
                context,
            )
            context["validate_ranch_entitlement"]()
            check.assert_called_once_with(
                context["STORE"], 2, "new-generation", context["character"]
            )

    def test_real_dispatch_guard_blocks_planting_and_actor_mutations_during_ranch(self):
        guard = _branch(
            lambda text: "ranch_session is not None" in text and "13578" in text
        )
        self.assertIn("Leave the ranch before this action", ast.unparse(guard))
        for opcode in (13220, 12995, 13578):
            with self.subTest(opcode=opcode):
                before = len(self.sent)
                result = _execute_branch(
                    guard,
                    globals_=self.globals,
                    locals_={
                        "loaded": True,
                        "ranch_session": object(),
                        "opcode": opcode,
                        "connection": self.globals["connection"],
                        "service": "world",
                    },
                )
                self.assertEqual(len(self.sent), before + 1)
                self.assertTrue(result["loaded"])

    def test_actual_hero_add_and_switch_branches_reject_active_ranch(self):
        for predicate, opcode, body, extra in (
            (
                lambda text: text == "opcode == 12219 and loaded",
                12219,
                struct.pack(">q", 11),
                {},
            ),
            (
                lambda text: text == "opcode == 12006 and loaded",
                12006,
                struct.pack(">q", 11),
                {"hero_switch_pending": None, "combat_session": None},
            ),
        ):
            branch = _branch(predicate)
            locals_ = {
                "opcode": opcode,
                "loaded": True,
                "body": body,
                "ranch_session": object(),
                "fight": None,
                "combat_session": None,
                "account_id": 2,
                "generation": "lease",
                "character": dict(self.actor),
                **extra,
            }
            before = len(self.sent)
            _execute_branch(branch, globals_=self.globals, locals_=locals_)
            self.assertGreaterEqual(len(self.sent), before + 2)
            self.assertTrue(
                any(
                    isinstance(event, tuple)
                    and event == ("record", "hero_add_rejected")
                    if opcode == 12219
                    else isinstance(event, tuple)
                    and event == ("record", "hero_switch_rejected")
                    for event in self.events
                )
            )

    def test_owned_hero_removal_branch_rejects_after_native_membership_check(self):
        class Result:
            def fetchone(self):
                return {"character_id": 11}

        class Database:
            def execute(self, query, params):
                self.query, self.params = query, params
                return Result()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        database = Database()
        original_store = self.globals["STORE"]
        self.globals["STORE"] = type(
            "Store",
            (),
            {
                "connection": staticmethod(lambda: database),
            },
        )()
        try:
            branch = _branch(
                lambda text: text == "opcode in (1156, 1031, 1074, 1066) and loaded"
            )
            _execute_branch(
                branch,
                globals_=self.globals,
                locals_={
                    "opcode": 1074,
                    "loaded": True,
                    "body": struct.pack(">qq", 99, 11),
                    "ranch_session": object(),
                    "account_id": 2,
                    "generation": "lease",
                    "character": dict(self.actor),
                    "connection": self.globals["connection"],
                    "service": "world",
                },
            )
        finally:
            self.globals["STORE"] = original_store
        self.assertIn("player_party_members", database.query)
        self.assertTrue(
            any(
                isinstance(event, tuple)
                and event == ("record", "party_request_rejected")
                for event in self.events
            )
        )

    def test_parent_bag_unwind_closes_ranch_before_parent_and_cleanup(self):
        branch = _branch(lambda text: text == "opcode == 12247 and loaded")
        statements = [ast.unparse(node) for node in branch.body]
        text = "\n".join(statements)
        self.assertLess(
            text.index("validate_ranch_lease()"),
            text.index("ranch_session.leave(character)"),
        )
        self.assertLess(
            text.index("ranch_session.leave(character)"),
            text.index("if bag_session is None"),
        )
        self.assertLess(
            text.index("ranch_session = None"),
            text.index("bag_session.leave(character)"),
        )
        self.assertLess(
            text.index("bag_session.leave(character)"), text.index("join_world(")
        )
        self.assertIn("PLANTINGS.cancel", text)
        self.assertIn("HARVESTS.cancel", text)

    def test_refresh_and_movement_dispatch_use_private_session_without_position_write(
        self,
    ):
        movement = _branch(
            lambda text: text
            == "active_private_session() is not None and active_private_session().owns(character)"
        )
        movement_text = ast.unparse(movement)
        self.assertIn("active_private_session().move(character, end)", movement_text)
        private_update_text = "\n".join(
            ast.unparse(statement) for statement in movement.body
        )
        self.assertNotIn("POSITIONS", private_update_text)
        self.assertIn("POSITIONS.move", ast.unparse(movement.orelse))

        refresh = _branch(lambda text: text == "opcode == 12580 and loaded")
        refresh_text = ast.unparse(ast.Module(body=refresh.body, type_ignores=[]))
        self.assertIn(
            "active_private_session().refresh(character, saved)", refresh_text
        )
        self.assertLess(
            refresh_text.index("save_haven_bag("),
            refresh_text.index("active_private_session().refresh(character, saved)"),
        )
        self.assertNotIn("POSITIONS.merge", refresh_text)


if __name__ == "__main__":
    unittest.main()
