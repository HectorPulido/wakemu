import struct
import unittest
from contextlib import contextmanager
import ast
from pathlib import Path
import uuid
from unittest.mock import DEFAULT, Mock, patch

from wakfu_server.characters import nation_state
from wakfu_server import environment_interactions as dispatcher_environment_interactions
from wakfu_server import nation_board as dispatcher_nation_board
from wakfu_server.maps import nation_board
from postgres_case import PostgresCase


BOARD_ID = 20158
MAP_ID = 527
BODY = struct.pack(">qHH", BOARD_ID, 28, 0)


class FakeDB:
    def __init__(self, populations=()):
        self.populations = populations
        self.queries = []

    def execute(self, query, params=()):
        self.queries.append((query, params))
        return self

    def fetchall(self):
        return [
            dict(nation_id=nation_id, population=count)
            for nation_id, count in self.populations
        ]


class FakeStore:
    def __init__(self, character, populations=()):
        self.db = FakeDB(populations)
        self.saved = character
        self.calls = []

    @contextmanager
    def connection(self):
        yield self.db

    def character(self, account_id, character_id, db):
        self.calls.append(("character", account_id, character_id))
        return self.saved


class NationBoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 12870 and len(body) == 12"
            and any(
                isinstance(child, ast.Attribute)
                and isinstance(child.value, ast.Name)
                and child.value.id == "nation_board"
                for child in ast.walk(node)
            )
        )
        following = None
        for parent in ast.walk(tree):
            for _, value in ast.iter_fields(parent):
                if isinstance(value, list) and branch in value:
                    index = value.index(branch)
                    following = value[index + 1]
                    break
            if following is not None:
                break
        wrapper = ast.For(
            target=ast.Name(id="_once", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=[branch, following],
            orelse=[],
        )
        cls.dispatch_code = compile(
            ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])),
            "<actual-nation-board-dispatch>",
            "exec",
        )

    def setUp(self):
        self.character = dict(
            id=77,
            map_id=MAP_ID,
            instance_id=0,
            x=90,
            y=0,
            z=5,
            level=1,
            nation_id=0,
        )
        self.rule = dict(
            id=BOARD_ID, type="NationSelectionBoard", map_id=MAP_ID, x=90, y=0, z=5
        )

    def test_definition_resolves_installed_identity_and_map(self):
        rows = (
            self.rule,
            dict(self.rule, id=BOARD_ID + 1, type="Other"),
        )
        with patch.object(
            nation_board.world_static,
            "objects",
            side_effect=lambda map_id: rows if map_id == MAP_ID else (),
        ) as objects:
            self.assertEqual(nation_board.definition(MAP_ID, BOARD_ID), self.rule)
            self.assertIsNone(nation_board.definition(MAP_ID + 1, BOARD_ID))
            objects.assert_any_call(MAP_ID)
            objects.assert_any_call(MAP_ID + 1)

    def test_native_board_is_installed_at_expected_astrub_position(self):
        resolved = nation_board.definition(MAP_ID, BOARD_ID)
        self.assertEqual(
            (
                resolved["id"],
                resolved["type"],
                resolved["map_id"],
                resolved["x"],
                resolved["y"],
                resolved["z"],
            ),
            (BOARD_ID, "NationSelectionBoard", MAP_ID, 90, 0, 5),
        )

    def test_request_is_exact_native_action_and_parameter(self):
        self.assertEqual(nation_board.request(BODY), BOARD_ID)
        for malformed in (
            bytearray(BODY),
            BODY[:-1],
            BODY + b"\0",
            struct.pack(">qHH", 0, 28, 0),
            struct.pack(">qHH", BOARD_ID, 27, 0),
            struct.pack(">qHH", BOARD_ID, 28, 1),
        ):
            with self.subTest(body=malformed), self.assertRaises(ValueError):
                nation_board.request(malformed)

    def test_open_selection_returns_existing_native_chooser_under_authority_checks(
        self,
    ):
        store = FakeStore(self.character, ((30, 3), (31, 1)))
        with patch.object(
            nation_board, "definition", return_value=self.rule
        ), patch.object(nation_board, "_lease") as lease, patch.object(
            nation_board, "_guard"
        ) as guard:
            result = nation_board.open_selection(store, 9, 4, self.character, BODY)

        self.assertEqual(result, nation_state.selection_packet({30: 3, 31: 1}))
        self.assertEqual(result[0], 14006)
        lease.assert_called_once_with(store, store.db, 9, 4, 77)
        guard.assert_called_once_with(store.db, 77)
        self.assertEqual(store.calls, [("character", 9, 77)])
        self.assertEqual(len(store.db.queries), 1)
        self.assertIn("character_chat_nations", store.db.queries[0][0])

    def test_rejects_occupation_uninstalled_board_and_invalid_scene_before_database(
        self,
    ):
        store = FakeStore(self.character)
        with patch.object(
            nation_board, "definition", return_value=self.rule
        ), patch.object(nation_board, "_lease") as lease:
            with self.assertRaises(ValueError):
                nation_board.open_selection(
                    store, 9, 4, self.character, BODY, blocked=True
                )
            self.assertEqual(store.db.queries, [])
            with patch.object(nation_board, "definition", return_value=None):
                with self.assertRaises(ValueError):
                    nation_board.open_selection(store, 9, 4, self.character, BODY)
            lease.assert_not_called()

            with self.assertRaises(ValueError):
                nation_board.open_selection(
                    store, 9, 4, dict(self.character, instance_id=17), BODY
                )
            with self.assertRaises(ValueError):
                nation_board.open_selection(
                    store, 9, 4, dict(self.character, x=95), BODY
                )
            with self.assertRaises(ValueError):
                nation_board.open_selection(
                    store, 9, 4, dict(self.character, z=float("inf")), BODY
                )
        self.assertEqual(store.db.queries, [])

    def test_session_and_combat_authorities_are_enforced(self):
        store = FakeStore(self.character)
        with patch.object(
            nation_board, "definition", return_value=self.rule
        ), patch.object(
            nation_board, "_lease", side_effect=ValueError("stale lease")
        ), patch.object(
            nation_board, "_guard"
        ) as guard:
            with self.assertRaisesRegex(ValueError, "stale lease"):
                nation_board.open_selection(store, 9, 4, self.character, BODY)
            guard.assert_not_called()

        with patch.object(
            nation_board, "definition", return_value=self.rule
        ), patch.object(nation_board, "_lease"), patch.object(
            nation_board, "_guard", side_effect=ValueError("combat")
        ):
            with self.assertRaisesRegex(ValueError, "combat"):
                nation_board.open_selection(store, 9, 4, self.character, BODY)
        self.assertEqual(store.calls, [])

    def test_existing_nation_and_level_zero_are_rejected(self):
        for saved in (
            dict(self.character, nation_id=30),
            dict(self.character, level=0),
        ):
            store = FakeStore(self.character)
            store.saved = saved
            with self.subTest(saved=saved), patch.object(
                nation_board, "definition", return_value=self.rule
            ), patch.object(nation_board, "_lease"), patch.object(
                nation_board, "_guard"
            ), self.assertRaises(
                ValueError
            ):
                nation_board.open_selection(store, 9, 4, self.character, BODY)
            self.assertEqual(store.db.queries, [])

    def dispatch_context(self):
        return dict(
            opcode=12870,
            body=BODY,
            character={"id": 77, "map_id": MAP_ID},
            account_id=9,
            generation=4,
            STORE=object(),
            environment_blocked=lambda: False,
            connection=object(),
            service="world",
            send=Mock(),
            record=Mock(),
            struct=struct,
            environment_ticket=None,
            publish_environment_scene=Mock(),
            world_static=Mock(),
        )

    def test_actual_dispatcher_opens_board_and_consumes_invalid_board_action(self):
        for behavior in ("success", "rejected"):
            context = self.dispatch_context()
            selection = (14006, b"chooser")
            with patch.object(
                dispatcher_nation_board,
                "definition",
                return_value=self.rule,
            ), patch.object(
                dispatcher_nation_board,
                "open_selection",
                return_value=selection if behavior == "success" else DEFAULT,
                side_effect=ValueError("invalid board action")
                if behavior == "rejected"
                else None,
            ) as opened:
                exec(self.dispatch_code, context)
            opened.assert_called_once()
            if behavior == "success":
                context["send"].assert_called_once_with(
                    context["connection"], "world", 14006, b"chooser"
                )
                context["record"].assert_not_called()
            else:
                context["send"].assert_not_called()
                self.assertEqual(
                    context["record"].call_args.kwargs["event"],
                    "nation_board_rejected",
                )

    def test_actual_dispatcher_falls_through_for_other_interactive_objects(self):
        context = self.dispatch_context()
        with patch.object(
            dispatcher_nation_board, "definition", return_value=None
        ), patch.object(
            dispatcher_nation_board, "open_selection"
        ) as opened, patch.object(
            dispatcher_environment_interactions,
            "definition",
            return_value={"kind": "switch"},
        ), patch.object(
            dispatcher_environment_interactions, "toggle", return_value=[]
        ) as toggle:
            exec(self.dispatch_code, context)
        opened.assert_not_called()
        toggle.assert_called_once()
        context["publish_environment_scene"].assert_called_once_with(force=True)


class NationBoardPostgresTests(PostgresCase):
    def test_selected_lease_citizenship_combat_and_proximity_are_enforced(self):
        account = self.store.register(
            "board" + uuid.uuid4().hex[:10], "local-test-password"
        )["id"]
        character = self.store.create_character(account, "Board Owner")
        sibling = self.store.create_character(account, "Board Sibling")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=90,y=0,z=5 "
                "WHERE id=%s",
                (character["id"],),
            )
            db.execute(
                "INSERT INTO character_chat_nations(character_id,nation_id) "
                "VALUES(%s,30)",
                (sibling["id"],),
            )
        character = self.store.character(account, character["id"])

        self.assertEqual(
            nation_board.open_selection(
                self.store, account, generation, character, BODY
            ),
            nation_state.selection_packet({30: 1}),
        )
        with self.assertRaises(ValueError):
            nation_board.open_selection(
                self.store, account, generation, dict(character, x=95), BODY
            )
        with self.assertRaises(ValueError):
            nation_board.open_selection(
                self.store, account, generation, dict(character, instance_id=4), BODY
            )

        stale_generation = generation
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.assertRaises(ValueError):
            nation_board.open_selection(
                self.store, account, stale_generation, character, BODY
            )

        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation,entry_hp,"
                "entry_max_hp,entry_hp_damage,entry_health_dead) "
                "VALUES(%s,%s,%s,0,%s,%s,%s,%s,%s)",
                (
                    fight_id,
                    character["id"],
                    account,
                    generation,
                    character["hp"],
                    character["max_hp"],
                    character["hp_damage"],
                    character["health_dead"],
                ),
            )
        with self.assertRaisesRegex(ValueError, "combat"):
            nation_board.open_selection(
                self.store, account, generation, character, BODY
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )

        nation_state.enroll(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">i", 31) + bytes(2),
        )
        with self.assertRaisesRegex(ValueError, "already belongs"):
            nation_board.open_selection(
                self.store, account, generation, character, BODY
            )


if __name__ == "__main__":
    unittest.main()
