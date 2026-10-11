import struct
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from wakfu_server.characters import nation_state
from wakfu_server.maps import nation_board


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


if __name__ == "__main__":
    unittest.main()
