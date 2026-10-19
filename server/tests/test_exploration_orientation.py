"""Native cnk12593 owns selected world facing, never a combat action."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import Mock

from postgres_case import PostgresCase
from wakfu_server.world_orientation import apply_exploration, decode_exploration_request
from wakfu_server.position_buffer import Positions
from wakfu_server.world import World


def extracted_exploration_orientation():
    """Execute the actual router branch with explicit session dependencies."""
    path = Path(__file__).resolve().parents[1] / "local_game_server.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    session = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "session"
    )
    branch = next(
        node
        for node in ast.walk(session)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "opcode"
        and any(
            isinstance(part, ast.Constant) and part.value == 12593
            for part in node.test.comparators
        )
    )
    branch = deepcopy(branch)
    branch.orelse = []
    names = (
        "opcode",
        "STORE",
        "POSITIONS",
        "WORLD",
        "account_id",
        "generation",
        "character",
        "body",
        "loaded",
        "fight",
        "record",
    )
    function = ast.FunctionDef(
        name="handle",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg=name) for name in names],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[branch, ast.Return(ast.Name(id="character", ctx=ast.Load()))],
        decorator_list=[],
    )
    namespace = {}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
            str(path),
            "exec",
        ),
        namespace,
    )
    return namespace["handle"]


class ExplorationOrientationDecoderTests(unittest.TestCase):
    def test_exact_native_planar_direction_byte(self):
        for direction in range(8):
            self.assertEqual(decode_exploration_request(bytes([direction])), direction)
        for body in (b"", b"\x01\x00", b"\x08", b"\x09", b"\xff", "1", 1):
            with self.subTest(body=body), self.assertRaises(ValueError):
                decode_exploration_request(body)

    def test_unloaded_combat_and_unauthenticated_requests_touch_no_authority(self):
        store, positions, world = Mock(), Mock(), Mock()
        for loaded, fight, account in (
            (False, None, 1),
            (True, object(), 1),
            (True, None, None),
            (True, None, True),
        ):
            with self.subTest(loaded=loaded, fight=fight, account=account):
                with self.assertRaises(ValueError):
                    apply_exploration(
                        store,
                        positions,
                        world,
                        account,
                        "lease",
                        {"id": 1},
                        b"\x01",
                        loaded=loaded,
                        fight=fight,
                    )
        self.assertEqual(store.mock_calls, [])
        self.assertEqual(positions.mock_calls, [])
        self.assertEqual(world.mock_calls, [])

    def test_actual_router_rejects_unloaded_unselected_session_without_side_effects(
        self,
    ):
        store, positions, world, record = Mock(), Mock(), Mock(), Mock()
        result = extracted_exploration_orientation()(
            12593,
            store,
            positions,
            world,
            None,
            None,
            None,
            b"\x01",
            False,
            None,
            record,
        )
        self.assertIsNone(result)
        self.assertEqual(record.call_args.kwargs["event"], "world_orientation_rejected")
        self.assertIsNone(record.call_args.kwargs["actor_id"])
        self.assertEqual(store.mock_calls, [])
        self.assertEqual(positions.mock_calls, [])
        self.assertEqual(world.mock_calls, [])


class ExplorationOrientationPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("exploration-direction", "test-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Explore Direction")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.character = self.store.character(self.account, self.character["id"])
        self.deliveries = []
        self.world = World(
            lambda character: ("spawn", character["id"]),
            lambda identity: ("remove", identity),
            lambda peer, opcode, body: self.deliveries.append((peer, opcode, body)),
        )
        self.world.join(self.generation, "owner", self.character)
        self.world.join("observer", "observer", dict(self.character, id=999999))
        self.deliveries.clear()

    def test_flushes_pending_walk_then_persists_and_broadcasts_native_facing(self):
        key = (self.account, self.generation, self.character["id"])
        positions = Positions(self.store, lease_active=lambda *lease: lease == key)
        positions.attach(*key[:2], self.character)
        walked = positions.move(
            *key,
            self.character,
            {
                **{axis: self.character[axis] for axis in ("x", "y", "z")},
                "x": self.character["x"] + 1,
                "direction": 6,
            }
        )
        self.world.update(self.generation, walked, 13331, b"walk", include_sender=False)
        self.deliveries.clear()
        events = []
        updated = extracted_exploration_orientation()(
            12593,
            self.store,
            positions,
            self.world,
            self.account,
            self.generation,
            walked,
            b"\x00",
            True,
            None,
            lambda **event: events.append(event),
        )
        saved = self.store.character(self.account, self.character["id"])
        self.assertEqual((walked["x"], 0), (saved["x"], saved["direction"]))
        self.assertEqual(updated["direction"], 0)
        self.assertEqual(
            events,
            [
                dict(
                    event="world_orientation",
                    actor_id=self.character["id"],
                    direction=0,
                )
            ],
        )
        self.assertFalse(positions.entries[key]["dirty"])
        self.assertEqual(
            {("owner", 12401), ("observer", 12401)},
            {(peer, opcode) for peer, opcode, _ in self.deliveries},
        )
        self.assertEqual(len({body for _, _, body in self.deliveries}), 1)

    def test_malformed_stale_and_foreign_selected_authorities_cannot_publish(self):
        foreign = self.store.create_character(self.account, "Other Direction")
        before = self.store.character(self.account, self.character["id"])["direction"]
        for body, generation, character in (
            (b"\x08", self.generation, self.character),
            (b"\x01\x02", self.generation, self.character),
            (b"\x01", "stale-generation", self.character),
            (b"\x01", self.generation, foreign),
        ):
            with self.subTest(body=body, identity=character["id"]):
                positions = Mock()
                with self.assertRaises(ValueError):
                    apply_exploration(
                        self.store,
                        positions,
                        self.world,
                        self.account,
                        generation,
                        character,
                        body,
                        loaded=True,
                        fight=None,
                    )
                positions.attach.assert_not_called()
                self.assertEqual(self.deliveries, [])
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["direction"],
            before,
        )

    def test_durable_active_fight_rejects_even_when_session_fight_is_absent(self):
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants "
                "(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s)",
                (fight, self.character["id"], self.account, self.generation),
            )
        positions = Mock()
        with self.assertRaisesRegex(ValueError, "outside actor"):
            apply_exploration(
                self.store,
                positions,
                self.world,
                self.account,
                self.generation,
                self.character,
                b"\x03",
                loaded=True,
                fight=None,
            )
        positions.attach.assert_not_called()
        self.assertEqual(self.deliveries, [])
