import ast
import struct
import unittest
from pathlib import Path

from postgres_case import PostgresCase
from wakfu_server.position_buffer import Positions
from wakfu_server.world import World


def extracted_world_orientation(namespace):
    source_path = Path(__file__).resolve().parents[1] / "local_game_server.py"
    tree = ast.parse(source_path.read_text(), filename=str(source_path))
    session = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "session"
    )
    branch = next(
        node
        for node in ast.walk(session)
        if isinstance(node, ast.If)
        and any(
            isinstance(value, ast.Compare)
            and isinstance(value.left, ast.Name)
            and value.left.id == "opcode"
            and any(
                isinstance(part, ast.Constant) and part.value == 13655
                for part in value.comparators
            )
            for value in ast.walk(node.test)
        )
        and any(
            isinstance(part, ast.Constant) and part.value is None
            for part in ast.walk(node.test)
        )
    )

    # The live dispatcher sits inside a packet loop. In this focused harness,
    # its `continue` means “return to the network loop”, so replace it with a
    # no-op and keep the branch's ordinary success/rejection effects.
    class RemoveContinue(ast.NodeTransformer):
        def visit_Continue(self, node):
            return ast.copy_location(ast.Pass(), node)

    branch = RemoveContinue().visit(branch)
    branch.orelse = []
    function = ast.FunctionDef(
        name="handle_world_orientation",
        args=ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(arg=name)
                for name in (
                    "opcode",
                    "fight",
                    "loaded",
                    "body",
                    "account_id",
                    "generation",
                    "character",
                    "STORE",
                    "WORLD",
                    "POSITIONS",
                    "record",
                )
            ],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[branch, ast.Return(value=ast.Name(id="character", ctx=ast.Load()))],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace["handle_world_orientation"]


class WorldOrientationDispatchTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account_id = self.store.register("direction-dispatch", "test-password")[
            "id"
        ]
        self.character = self.store.create_character(
            self.account_id, "Direction Dispatch"
        )
        self.generation = self.store.begin_session(self.account_id)
        self.store.select_character(
            self.account_id, self.generation, self.character["id"]
        )
        self.character = self.store.character(self.account_id, self.character["id"])
        self.deliveries = []
        self.world = World(
            lambda character: ("spawn", character["id"]),
            lambda identity: ("remove", identity),
            lambda peer, opcode, body: self.deliveries.append((peer, opcode, body)),
        )

    def _handler(self, *, peer_locations=True):
        self.world.join(self.generation, "owner", self.character)
        observer = dict(self.character, id=self.character["id"] + 1000)
        if not peer_locations:
            observer["instance_id"] += 1
        self.world.join("observer-session", "observer", observer)
        self.deliveries.clear()
        events = []
        position_events = []

        class Positions:
            def flush(_self, **values):
                position_events.append(("flush", values))

            def attach(_self, account_id, generation, character):
                position_events.append(
                    ("attach", account_id, generation, character["direction"])
                )

        handler = extracted_world_orientation({})
        return handler, events, position_events

    def test_actual_dispatcher_persists_and_fans_out_world_direction_only_here(self):
        handler, events, position_events = self._handler()
        direction = 5
        updated = handler(
            opcode=13655,
            fight=None,
            loaded=True,
            body=struct.pack(">qB", self.character["id"], direction),
            account_id=self.account_id,
            generation=self.generation,
            character=self.character,
            STORE=self.store,
            WORLD=self.world,
            POSITIONS=type(
                "PositionBuffer",
                (),
                {
                    "flush": lambda _self, **values: position_events.append(
                        ("flush", values)
                    ),
                    "attach": lambda _self, account_id, generation, character: position_events.append(
                        ("attach", account_id, generation, character["direction"])
                    ),
                },
            )(),
            record=lambda **event: events.append(event),
        )
        self.assertEqual(direction, updated["direction"])
        self.assertEqual(1, len(events))
        self.assertEqual(["flush", "attach"], [event[0] for event in position_events])
        self.assertEqual(
            {("owner", 12401), ("observer", 12401)},
            {(peer, opcode) for peer, opcode, _ in self.deliveries},
        )
        self.assertEqual(1, len({body for _, _, body in self.deliveries}))
        self.assertEqual(
            direction,
            self.store.character(self.account_id, self.character["id"])["direction"],
        )
        self.assertEqual(
            direction,
            {c["id"]: c for c in self.world.snapshot()}[self.character["id"]][
                "direction"
            ],
        )

    def test_different_instance_observer_and_wrong_actor_receive_no_direction_update(
        self,
    ):
        handler, events, position_events = self._handler(peer_locations=False)
        positions = type(
            "PositionBuffer",
            (),
            {
                "flush": lambda _self, **values: position_events.append(
                    ("flush", values)
                ),
                "attach": lambda _self, account_id, generation, character: position_events.append(
                    ("attach", account_id, generation, character["direction"])
                ),
            },
        )()
        handler(
            opcode=13655,
            fight=None,
            loaded=True,
            body=struct.pack(">qB", self.character["id"], 7),
            account_id=self.account_id,
            generation=self.generation,
            character=self.character,
            STORE=self.store,
            WORLD=self.world,
            POSITIONS=positions,
            record=lambda **event: events.append(event),
        )
        self.assertEqual([("owner", 12401)], [event[:2] for event in self.deliveries])
        self.deliveries.clear()
        before = self.store.character(self.account_id, self.character["id"])[
            "direction"
        ]
        handler(
            opcode=13655,
            fight=None,
            loaded=True,
            body=struct.pack(">qB", self.character["id"] + 1, 3),
            account_id=self.account_id,
            generation=self.generation,
            character=self.character,
            STORE=self.store,
            WORLD=self.world,
            POSITIONS=positions,
            record=lambda **event: events.append(event),
        )
        self.assertEqual([], self.deliveries)
        self.assertEqual(
            before,
            self.store.character(self.account_id, self.character["id"])["direction"],
        )
        self.assertEqual("world_orientation_rejected", events[-1]["event"])

    def test_manual_turn_flushes_pending_walk_before_direction_cas_write(self):
        self.world.join(self.generation, "owner", self.character)
        observer = dict(self.character, id=self.character["id"] + 1000)
        self.world.join("observer-session", "observer", observer)
        self.deliveries.clear()
        key = (self.account_id, self.generation, self.character["id"])
        positions = Positions(self.store, lease_active=lambda *lease: lease == key)
        positions.attach(self.account_id, self.generation, self.character)

        walked = positions.move(
            self.account_id,
            self.generation,
            self.character["id"],
            self.character,
            {
                **{axis: self.character[axis] for axis in ("x", "y", "z")},
                "x": self.character["x"] + 1,
                "direction": 6,
            },
        )
        # The movement handler publishes the buffered position in its in-memory
        # world snapshot; PostgreSQL still holds the pre-walk CAS baseline.
        self.world.update(self.generation, walked, 13331, b"walk", include_sender=False)
        self.deliveries.clear()

        events = []
        handler = extracted_world_orientation({})
        updated = handler(
            opcode=13655,
            fight=None,
            loaded=True,
            body=struct.pack(">qB", self.character["id"], 5),
            account_id=self.account_id,
            generation=self.generation,
            character=walked,
            STORE=self.store,
            WORLD=self.world,
            POSITIONS=positions,
            record=lambda **event: events.append(event),
        )

        saved = self.store.character(self.account_id, self.character["id"])
        self.assertEqual((walked["x"], 5), (saved["x"], saved["direction"]), events)
        self.assertEqual((walked["x"], 5), (updated["x"], updated["direction"]))
        self.assertFalse(positions.entries[key]["dirty"])
        self.assertEqual(
            (walked["x"], 5),
            (
                positions.entries[key]["current"]["x"],
                positions.entries[key]["current"]["direction"],
            ),
        )
        self.assertEqual(
            {("owner", 12401), ("observer", 12401)},
            {(peer, opcode) for peer, opcode, _ in self.deliveries},
        )
        self.assertEqual(1, len({body for _, _, body in self.deliveries}))
        self.assertEqual(1, len(events))
