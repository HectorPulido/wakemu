"""Focused native codec and authority tests for ordinary public doors."""
import ast
import hashlib
from pathlib import Path
import struct
import sys
import time
import unittest
import uuid
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from wakfu_server import world_static
from wakfu_server import environment_interactions as dispatcher_environment_interactions
from wakfu_server import environment_seats, world_scene_sync
from wakfu_server import environment_doors as doors
from postgres_case import PostgresCase


def native_payload(state=0):
    payload = bytearray.fromhex("0102000000060200010102030405060708090a")
    payload[7:9] = struct.pack(">h", state)
    payload[12:14] = bytes((state, state))
    return bytes(payload)


def rule(state=0, *, map_id=143, identity=12345):
    payload = native_payload(state)
    return {
        "map_id": map_id,
        "object_id": identity,
        "x": 10,
        "y": 20,
        "z": 3,
        "initial_state": state,
        "payload_sha256": hashlib.sha256(native_payload(0)).hexdigest(),
        "state_payload_hex": payload.hex(),
    }


class FakeDB:
    def __init__(self, definition_row=None, state=0, occupied=False):
        self.definition_row = definition_row
        self.state = state
        self.occupied = occupied
        self.statements = []

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        if "SELECT * FROM environment_door_definitions" in sql:
            return FakeCursor(self.definition_row)
        if "SELECT state FROM environment_door_states" in sql:
            return FakeCursor({"state": self.state})
        if "SELECT 1 FROM characters c JOIN sessions" in sql:
            return FakeCursor({"occupied": 1} if self.occupied else None)
        if "INSERT INTO environment_door_states" in sql:
            self.state = params[-1]
        return FakeCursor(None)


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        if isinstance(self.row, dict) and "occupied" in self.row:
            return {"1": 1}
        return self.row

    def fetchall(self):
        return self.row if isinstance(self.row, list) else []


class FakeStore:
    def __init__(self, db):
        self.db = db

    def connection(self):
        return self

    def __enter__(self):
        return self.db

    def __exit__(self, *_):
        return False

    def now(self):
        return "2099-01-01T00:00:00Z"


class EnvironmentDoorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(
            (ROOT / "server/local_game_server.py").read_text(encoding="utf8")
        )
        session = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        branch = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 12870 and len(body) == 12"
            and any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "environment_doors"
                and call.func.attr == "interact"
                for call in ast.walk(node)
            )
        )
        following = None
        for parent in ast.walk(tree):
            for _, value in ast.iter_fields(parent):
                if isinstance(value, list) and branch in value:
                    following = value[value.index(branch) + 1]
                    break
            if following is not None:
                break
        if following is None:
            raise AssertionError("ordinary-door dispatcher has no following branch")
        wrapper = ast.For(
            target=ast.Name(id="_once", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=[branch, following],
            orelse=[],
        )
        cls.dispatch_code = compile(
            ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])),
            "<actual-ordinary-door-dispatch>",
            "exec",
        )
        movement_branch = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and "opcode == 13331 and loaded" in ast.unparse(node.test)
        )
        movement_try = next(
            node
            for node in ast.walk(movement_branch)
            if isinstance(node, ast.Try)
            and any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "environment_doors"
                and call.func.attr == "validate_movement"
                for call in ast.walk(node)
            )
        )
        movement_commit = next(
            node
            for node in ast.walk(movement_branch)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "movement_state"
            and node.func.attr == "commit"
        )
        cls.movement_code = compile(
            ast.fix_missing_locations(
                ast.Module(
                    body=[
                        ast.For(
                            target=ast.Name(id="_once", ctx=ast.Store()),
                            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                            body=[movement_try, ast.Expr(value=movement_commit)],
                            orelse=[],
                        )
                    ],
                    type_ignores=[],
                )
            ),
            "<actual-door-movement-validation>",
            "exec",
        )
        publisher = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.FunctionDef)
            and node.name == "publish_environment_scene"
        )
        outer = ast.FunctionDef(
            name="_publisher_fixture",
            args=ast.arguments(
                posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
            ),
            body=[
                ast.Assign(
                    targets=[
                        ast.Name(id="environment_scene_identity", ctx=ast.Store())
                    ],
                    value=ast.Constant(None),
                ),
                ast.Assign(
                    targets=[ast.Name(id="environment_scene_states", ctx=ast.Store())],
                    value=ast.Dict(keys=[], values=[]),
                ),
                ast.Assign(
                    targets=[ast.Name(id="last_environment_refresh", ctx=ast.Store())],
                    value=ast.Constant(0.0),
                ),
                ast.Assign(
                    targets=[ast.Name(id="loaded", ctx=ast.Store())],
                    value=ast.Constant(True),
                ),
                ast.Assign(
                    targets=[ast.Name(id="character", ctx=ast.Store())],
                    value=ast.Dict(
                        keys=[
                            ast.Constant(key)
                            for key in ("id", "map_id", "instance_id", "x", "y", "z")
                        ],
                        values=[
                            ast.Constant(value) for value in (77, 143, 0, 10, 19, 3)
                        ],
                    ),
                ),
                *[
                    ast.Assign(
                        targets=[ast.Name(id=name, ctx=ast.Store())],
                        value=ast.Constant(None),
                    )
                    for name in ("fight", "combat_session", "spectator_session")
                ],
                publisher,
                ast.Return(
                    value=ast.Name(id="publish_environment_scene", ctx=ast.Load())
                ),
            ],
            decorator_list=[],
        )
        cls.publisher_code = compile(
            ast.fix_missing_locations(ast.Module(body=[outer], type_ignores=[])),
            "<actual-environment-scene-publisher>",
            "exec",
        )

    def setUp(self):
        self.character = {
            "id": 77,
            "map_id": 143,
            "instance_id": 0,
            "x": 10,
            "y": 19,
            "z": 3,
        }
        self.native = {
            "id": 12345,
            "type": "Door",
            "payload_hex": native_payload(0).hex(),
        }

    def body(self, action, *, identity=12345, parameter=0):
        return struct.pack(">qHH", identity, action, parameter)

    def test_native_request_accepts_only_open_and_close_actions(self):
        self.assertEqual((12345, 0), doors.request(self.body(17)))
        self.assertEqual((12345, 1), doors.request(self.body(18)))
        for body in (
            b"",
            self.body(17)[:-1],
            self.body(17, identity=0),
            self.body(16),
            self.body(17, parameter=1),
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                doors.request(body)

    def test_open_close_12344_payload_preserves_original_flags_and_tail(self):
        source = bytes.fromhex("01020000000602000101010001010000000000")
        definition = rule(state=1)
        definition["state_payload_hex"] = source.hex()
        for state in (0, 1):
            with self.subTest(state=state):
                opcode, packet = doors.state_packet(definition, state)
                identity, size = struct.unpack(">qH", packet[:10])
                result = packet[10:]
                expected = bytearray(source)
                expected[7:9] = struct.pack(">h", state)
                expected[12:14] = bytes((state, state))
                self.assertEqual(12344, opcode)
                self.assertEqual((12345, 19), (identity, size))
                self.assertEqual(bytes(expected), result)
                self.assertEqual(source[:7], result[:7])
                self.assertEqual(source[9:12], result[9:12])
                self.assertEqual(source[14:], result[14:])
        for invalid in (True, -1, 2, "0"):
            with self.assertRaises(ValueError):
                doors.state_packet(definition, invalid)

    def test_definition_requires_native_door_and_exact_payload_hash(self):
        db = FakeDB(rule())
        store = FakeStore(db)
        with patch.object(world_static, "objects", return_value=[self.native]):
            self.assertEqual(rule(), doors.definition(store, 143, 12345))
        with patch.object(world_static, "objects", return_value=[]):
            with self.assertRaisesRegex(ValueError, "admitted"):
                doors._qualified(rule(), 143, 12345)
        mismatched = rule()
        mismatched["payload_sha256"] = "0" * 64
        with patch.object(world_static, "objects", return_value=[self.native]):
            with self.assertRaisesRegex(ValueError, "different native catalog"):
                doors._qualified(mismatched, 143, 12345)

    def test_interaction_authority_guards_private_occupation_combat_and_range(self):
        db = FakeDB(rule())
        store = FakeStore(db)
        with self.assertRaisesRegex(ValueError, "scene"):
            doors.interact(
                store, 5, 9, dict(self.character, instance_id=4), self.body(17)
            )
        with self.assertRaisesRegex(ValueError, "scene"):
            doors.interact(store, 5, 9, self.character, self.body(17), blocked=True)
        with patch.object(doors, "_lease", side_effect=ValueError("stale session")):
            with self.assertRaisesRegex(ValueError, "stale session"):
                doors.interact(store, 5, 9, self.character, self.body(17))
        with patch.object(doors, "_lease"), patch.object(
            doors, "_guard", side_effect=ValueError("combat")
        ):
            with self.assertRaisesRegex(ValueError, "combat"):
                doors.interact(store, 5, 9, self.character, self.body(17))
        with patch.object(doors, "_lease"), patch.object(doors, "_guard"):
            with patch.object(doors, "_position", side_effect=ValueError("range")):
                with patch.object(world_static, "objects", return_value=[self.native]):
                    with self.assertRaisesRegex(ValueError, "range"):
                        doors.interact(store, 5, 9, self.character, self.body(17))

    def test_occupied_door_cell_cannot_be_closed(self):
        db = FakeDB(rule(state=0), occupied=True)
        store = FakeStore(db)
        with patch.object(doors, "_lease"), patch.object(doors, "_guard"), patch.object(
            doors, "_position"
        ), patch.object(world_static, "objects", return_value=[self.native]):
            with self.assertRaisesRegex(ValueError, "occupied"):
                doors.interact(store, 5, 9, self.character, self.body(18))

    def test_open_close_replay_and_idempotent_native_snapshot(self):
        db = FakeDB(rule(state=1), state=1)
        store = FakeStore(db)
        with patch.object(doors, "_lease"), patch.object(doors, "_guard"), patch.object(
            doors, "_position"
        ), patch.object(world_static, "objects", return_value=[self.native]):
            opened = doors.interact(store, 5, 9, self.character, self.body(17))
            closed = doors.interact(store, 5, 9, self.character, self.body(18))
        self.assertEqual((0, False), (opened["state"], opened["replay"]))
        self.assertEqual((1, False), (closed["state"], closed["replay"]))
        self.assertEqual(12344, opened["packet"][0])
        self.assertEqual(12344, closed["packet"][0])
        self.assertTrue(any("ON CONFLICT" in sql for sql, _ in db.statements))

    def test_movement_blocks_closed_cells_and_diagonal_corner_but_allows_open(self):
        closed_row = rule(state=1)
        open_row = rule(state=0, identity=12346)
        movement = {
            "start_position": {"x": 9, "y": 19, "z": 3},
            "steps": [{"dx": 1, "dy": 0, "dz": 0}],
        }
        closed_row.update(x=10, y=19)
        with patch.object(doors, "_states", return_value=((closed_row, 1),)):
            with self.assertRaisesRegex(ValueError, "crosses"):
                doors.validate_movement(FakeStore(FakeDB()), self.character, movement)
        leave_closed = {
            "start_position": {"x": 10, "y": 19, "z": 3},
            "steps": [{"dx": -1, "dy": 0, "dz": 0}],
        }
        with patch.object(doors, "_states", return_value=((closed_row, 1),)):
            self.assertEqual(
                (9, 19, 3),
                doors.validate_movement(
                    FakeStore(FakeDB()), self.character, leave_closed
                ),
            )
        diagonal = {
            "start_position": {"x": 9, "y": 19, "z": 3},
            "steps": [{"dx": 1, "dy": 1, "dz": 0}],
        }
        corner = rule(state=1)
        corner.update(x=10, y=19)
        with patch.object(doors, "_states", return_value=((corner, 1),)):
            with self.assertRaisesRegex(ValueError, "Diagonal"):
                doors.validate_movement(FakeStore(FakeDB()), self.character, diagonal)
        open_row.update(x=10, y=19)
        with patch.object(doors, "_states", return_value=((open_row, 0),)):
            self.assertEqual(
                (10, 19, 3),
                doors.validate_movement(FakeStore(FakeDB()), self.character, movement),
            )

    def test_snapshots_select_requested_native_objects_and_current_state(self):
        closed = rule(state=1, identity=12345)
        opened = rule(state=0, identity=12346)
        with patch.object(doors, "_states", return_value=((closed, 1), (opened, 0))):
            all_packets = doors.snapshots(FakeStore(FakeDB()), 143, 0)
            selected = doors.snapshots(FakeStore(FakeDB()), 143, 0, {12346})
        self.assertEqual([12344, 12344], [opcode for opcode, _ in all_packets])
        self.assertEqual(
            [12345, 12346],
            [struct.unpack(">q", body[:8])[0] for _, body in all_packets],
        )
        self.assertEqual(
            [12346], [struct.unpack(">q", body[:8])[0] for _, body in selected]
        )
        self.assertEqual(1, struct.unpack(">h", all_packets[0][1][17:19])[0])
        self.assertEqual(0, struct.unpack(">h", all_packets[1][1][17:19])[0])

    def test_same_state_close_is_an_idempotent_replay(self):
        db = FakeDB(rule(state=0), state=1)
        with patch.object(doors, "_lease"), patch.object(doors, "_guard"), patch.object(
            doors, "_position"
        ), patch.object(world_static, "objects", return_value=[self.native]):
            result = doors.interact(FakeStore(db), 5, 9, self.character, self.body(18))
        self.assertEqual((1, True), (result["state"], result["replay"]))

    def test_private_instances_do_not_receive_global_door_blocks(self):
        private = dict(self.character, instance_id=98)
        store = FakeStore(FakeDB())
        with patch.object(
            store, "connection", side_effect=AssertionError("queried private state")
        ):
            self.assertEqual(
                (11, 19, 3),
                doors.validate_movement(
                    store,
                    private,
                    {
                        "start_position": {"x": 10, "y": 19, "z": 3},
                        "steps": [{"dx": 1, "dy": 0, "dz": 0}],
                    },
                ),
            )

    def test_dispatcher_gate_if_integrated_validates_before_movement_commit(self):
        """The live movement branch checks door cells before committing position."""
        source = (ROOT / "server/local_game_server.py").read_text(encoding="utf8")
        tree = ast.parse(source)
        session = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        movement = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and "opcode == 13331 and loaded" in ast.unparse(node.test)
        )
        calls = [
            node
            for node in ast.walk(movement)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "validate_movement"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "environment_doors"
        ]
        commits = [
            node
            for node in ast.walk(movement)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "commit"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "movement_state"
        ]
        self.assertEqual(1, len(calls), "missing ordinary-door movement gate")
        self.assertTrue(commits, "movement branch has no commit gate")
        self.assertLess(calls[0].lineno, min(node.lineno for node in commits))

    def test_dispatcher_handles_only_qualified_non_dungeon_native_doors(self):
        tree = ast.parse(
            (ROOT / "server/local_game_server.py").read_text(encoding="utf8")
        )
        session = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        branches = [
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 12870 and len(body) == 12"
            and any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "environment_doors"
                and call.func.attr == "interact"
                for call in ast.walk(node)
            )
        ]
        self.assertEqual(1, len(branches))
        branch = branches[0]
        calls = [
            node
            for node in ast.walk(branch)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        names = {(node.func.attr, ast.unparse(node.func.value)) for node in calls}
        self.assertIn(("definition", "environment_doors"), names)
        self.assertIn(("interact", "environment_doors"), names)
        self.assertTrue(
            any(
                ast.unparse(node.test).find("is_dungeon_run") >= 0
                for node in ast.walk(branch)
                if isinstance(node, ast.If)
            )
        )
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "publish_environment_scene"
                for node in ast.walk(branch)
            )
        )

    def test_scene_sync_publishes_nearby_door_snapshots(self):
        tree = ast.parse(
            (ROOT / "server/local_game_server.py").read_text(encoding="utf8")
        )
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "door_snapshots"
        ]
        self.assertTrue(calls, "no ordinary-door state snapshot integration")
        self.assertTrue(any(len(node.args) == 4 for node in calls))

    def _dispatch_context(self, *, map_id=143, instance_id=0):
        return dict(
            opcode=12870,
            body=struct.pack(">qHH", 12345, 17, 0),
            character=dict(self.character, map_id=map_id, instance_id=instance_id),
            account_id=5,
            generation=9,
            STORE=object(),
            environment_blocked=lambda: False,
            is_dungeon_run=lambda value: value != 0,
            world_static=world_static,
            connection=object(),
            service="world",
            send=Mock(),
            record=Mock(),
            publish_environment_scene=Mock(),
            environment_ticket=None,
            struct=struct,
        )

    def test_actual_dispatcher_sends_owner_packet_and_consumes_rejection(self):
        native_door = dict(self.native, map_id=143, x=10, y=20, z=3)
        for outcome in ("success", "rejected"):
            context = self._dispatch_context()
            with patch.object(
                world_static, "objects", return_value=[native_door]
            ), patch.object(doors, "definition", return_value=rule()), patch.object(
                doors,
                "interact",
                return_value={"packet": (12344, b"native-state")}
                if outcome == "success"
                else Mock(side_effect=ValueError("denied")),
            ) as interact, patch.object(
                dispatcher_environment_interactions, "definition"
            ) as generic:
                if outcome == "rejected":
                    # The patched mock is the interaction callable and throws on call.
                    interact.side_effect = ValueError("denied")
                exec(self.dispatch_code, context)
            interact.assert_called_once()
            generic.assert_not_called()
            if outcome == "success":
                context["send"].assert_called_once_with(
                    context["connection"], "world", 12344, b"native-state"
                )
                context["publish_environment_scene"].assert_called_once_with(force=True)
                context["record"].assert_not_called()
            else:
                context["send"].assert_not_called()
                context["publish_environment_scene"].assert_not_called()
                context["record"].assert_called_once()
        private = self._dispatch_context(map_id=9, instance_id=812)
        with patch.object(
            world_static, "objects", return_value=[self.native]
        ), patch.object(
            doors, "definition", return_value=rule()
        ) as definition, patch.object(
            doors, "interact"
        ) as interact:
            exec(self.dispatch_code, private)
        definition.assert_not_called()
        interact.assert_not_called()

    def test_actual_movement_try_commits_only_after_door_validation(self):
        movement = {"mode_id": 2, "steps": [{"direction": 1}]}
        state = Mock()
        context = dict(
            movement_state=state,
            movement=movement,
            STORE=object(),
            character=self.character,
            DUNGEON_ROOM_RUNTIME_AVAILABLE=False,
            is_dungeon_run=lambda _instance_id: False,
            record=Mock(),
            send=Mock(),
            connection=object(),
            service="world",
            position={"x": 10, "y": 19, "z": 3},
            struct=struct,
        )
        state.validate.return_value = "approved"
        with patch.object(doors, "validate_movement") as validate:
            exec(self.movement_code, context)
        validate.assert_called_once()
        state.commit.assert_called_once_with("approved")

        state.reset_mock()
        context["send"].reset_mock()
        context["record"].reset_mock()
        with patch.object(
            doors, "validate_movement", side_effect=ValueError("closed door")
        ):
            exec(self.movement_code, context)
        state.validate.assert_called_once_with(movement)
        state.commit.assert_not_called()
        context["send"].assert_called_once()
        self.assertEqual(13530, context["send"].call_args.args[2])
        context["record"].assert_called_once()

    def test_actual_scene_publisher_sends_own_nearby_door_snapshot(self):
        context = {
            "time": time,
            "struct": struct,
            "world_static": world_static,
            "STORE": FakeStore(FakeDB()),
            "connection": object(),
            "service": "world",
            "send": Mock(),
        }
        exec(self.publisher_code, context)
        publish = context["_publisher_fixture"]()
        native_door = dict(self.native, map_id=143, x=10.0, y=19.0, z=3.0)
        payload = bytes.fromhex("01020000000602000101010001010000000000")
        packet = (12344, struct.pack(">qH", 12345, len(payload)) + payload)
        with patch.object(
            world_static, "objects", return_value=[native_door]
        ), patch.object(world_scene_sync, "chunk", return_value=(0, 0)), patch.object(
            world_scene_sync, "neighborhood", return_value={(0, 0)}
        ), patch.object(
            dispatcher_environment_interactions, "snapshots", return_value=()
        ), patch.object(
            environment_seats, "snapshots", return_value=()
        ), patch.object(
            doors, "snapshots", return_value=(packet,)
        ) as snapshots:
            publish(force=True)
        snapshots.assert_called_once_with(context["STORE"], 143, 0, {12345})
        context["send"].assert_called_once_with(context["connection"], "world", *packet)


class EnvironmentDoorPostgresTests(PostgresCase):
    def test_fresh_migration_143_seeds_only_native_payload_qualified_doors(self):
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT map_id,object_id,x,y,z,initial_state,payload_sha256,state_payload_hex "
                "FROM environment_door_definitions ORDER BY map_id,object_id"
            ).fetchall()
        self.assertEqual(33, len(rows))
        selected = next(
            row for row in rows if (row["map_id"], row["object_id"]) == (337, 15411)
        )
        self.assertEqual(
            (51, -245, 4, 1),
            (selected["x"], selected["y"], selected["z"], selected["initial_state"]),
        )
        checked = 0
        for row in rows:
            native = next(
                (
                    obj
                    for obj in world_static.objects(row["map_id"])
                    if obj["id"] == row["object_id"] and obj["type"] == "Door"
                ),
                None,
            )
            self.assertIsNotNone(native, (row["map_id"], row["object_id"]))
            self.assertEqual(
                hashlib.sha256(bytes.fromhex(native["payload_hex"])).hexdigest(),
                row["payload_sha256"],
            )
            self.assertEqual(19, len(bytes.fromhex(row["state_payload_hex"])))
            checked += 1
        self.assertEqual(33, checked)

        account = self.store.register("door" + uuid.uuid4().hex[:12], "test-password")[
            "id"
        ]
        character = self.store.create_character(
            account,
            "Door"
            + "".join(
                chr(ord("a") + int(value, 16)) for value in uuid.uuid4().hex[:10]
            ),
        )
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=337,instance_id=0,x=51,y=-245,z=4 WHERE id=%s",
                (character["id"],),
            )
        character.update(map_id=337, instance_id=0, x=51, y=-245, z=4)
        door_id = 15411
        adjacent = dict(character, y=-246)

        # A player already occupying the closed cell can always leave it, and
        # prevents another close request from claiming the cell.
        leave = {
            "start_position": {"x": 51, "y": -245, "z": 4},
            "steps": [{"dx": 0, "dy": -1, "dz": 0}],
        }
        self.assertEqual(
            (51, -246, 4), doors.validate_movement(self.store, character, leave)
        )
        with self.assertRaisesRegex(ValueError, "occupied"):
            doors.interact(
                self.store,
                account,
                generation,
                character,
                struct.pack(">qHH", door_id, 18, 0),
            )

        with self.store.connection() as db:
            db.execute("UPDATE characters SET y=-246 WHERE id=%s", (character["id"],))
        character.update(adjacent)
        opened = doors.interact(
            self.store,
            account,
            generation,
            character,
            struct.pack(">qHH", door_id, 17, 0),
        )
        self.assertEqual((0, False), (opened["state"], opened["replay"]))
        self.assertEqual(12344, opened["packet"][0])
        snapshot = doors.snapshots(self.store, 337, 0, {door_id})
        self.assertEqual(1, len(snapshot))
        self.assertEqual(opened["packet"], snapshot[0])
        enter = {
            "start_position": {"x": 51, "y": -246, "z": 4},
            "steps": [{"dx": 0, "dy": 1, "dz": 0}],
        }
        self.assertEqual(
            (51, -245, 4), doors.validate_movement(self.store, adjacent, enter)
        )

        with self.store.connection() as db:
            db.execute("UPDATE characters SET y=-245 WHERE id=%s", (character["id"],))
        character.update(y=-245)
        with self.assertRaisesRegex(ValueError, "occupied"):
            doors.interact(
                self.store,
                account,
                generation,
                character,
                struct.pack(">qHH", door_id, 18, 0),
            )
        self.assertEqual(
            (51, -246, 4), doors.validate_movement(self.store, character, leave)
        )

        with self.store.connection() as db:
            db.execute("UPDATE characters SET y=-246 WHERE id=%s", (character["id"],))
        character.update(y=-246)
        closed = doors.interact(
            self.store,
            account,
            generation,
            character,
            struct.pack(">qHH", door_id, 18, 0),
        )
        self.assertEqual((1, False), (closed["state"], closed["replay"]))
        with self.assertRaisesRegex(ValueError, "crosses"):
            doors.validate_movement(self.store, character, enter)

        stale_generation = generation
        replacement = self.store.begin_session(account, ttl=10_000)
        self.store.select_character(account, replacement, character["id"])
        with self.assertRaises(ValueError):
            doors.interact(
                self.store,
                account,
                stale_generation,
                character,
                struct.pack(">qHH", door_id, 17, 0),
            )


if __name__ == "__main__":
    unittest.main()
