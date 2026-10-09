import struct
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.characters.captured_roster import OwnedCapturedRoster
from wakfu_server.characters.captured_roster_selection import select


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(
            id=7,
            account_id=8,
            breed=2,
            captured_roster=OwnedCapturedRoster(7).to_record(),
        )
        self.store = SimpleNamespace(
            connection=lambda: self.fail("Unexpected database access")
        )

    def test_malformed_and_foreign_requests_do_not_access_storage(self):
        for body in (
            b"",
            b"\x00" * 8,
            b"\x00" * 10,
            struct.pack(">qb", 9, 0),
            struct.pack(">qb", 7, -1),
            struct.pack(">qb", 7, 10),
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                select(self.store, 8, self.character, body)
        with self.assertRaises(ValueError):
            select(self.store, 99, self.character, struct.pack(">qb", 7, 0))

    def test_combat_stages_selection_without_database_or_character_mutation(self):
        source = OwnedCapturedRoster(7, available=(True,) * 10).to_record()
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(controlled=True, owner_id=8)},
            native_captured_rosters={"7": source},
        )
        before = dict(self.character["captured_roster"])
        result = select(
            self.store, 8, self.character, struct.pack(">qb", 7, 4), fight=fight
        )
        self.assertEqual(result["selected_slot"], 4)
        self.assertEqual(result["available"], [True] * 10)
        self.assertEqual(result["slots"], source["slots"])
        self.assertEqual(fight.native_captured_roster_updates, {"7": result})
        self.assertEqual(fight.native_captured_rosters, {"7": result})
        self.assertEqual(self.character["captured_roster"], before)
        self.assertEqual(source["selected_slot"], 0)

    def test_foreign_combat_actor_cannot_stage_update(self):
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(controlled=True, owner_id=99)}
        )
        with self.assertRaises(ValueError):
            select(self.store, 8, self.character, struct.pack(">qb", 7, 1), fight=fight)
        self.assertFalse(hasattr(fight, "native_captured_roster_updates"))

    def test_exploration_saves_inside_owner_locked_transaction(self):
        events = []

        class Database:
            @contextmanager
            def transaction(self):
                events.append("begin")
                yield
                events.append("commit")

            def execute(self, sql, parameters):
                self_test.assertIn("FOR UPDATE", sql)
                self_test.assertEqual(parameters, (7, 8))
                events.append("lock")
                return SimpleNamespace(fetchone=lambda: {"id": 7})

        self_test = self

        @contextmanager
        def connection():
            yield Database()

        def load(db, character):
            events.append("load")
            return self.character["captured_roster"]

        def save(db, character, roster):
            events.append(("save", roster.selected_slot))

        with patch(
            "wakfu_server.characters.captured_roster_selection.load", load
        ), patch("wakfu_server.characters.captured_roster_selection.save", save):
            result = select(
                SimpleNamespace(connection=connection),
                8,
                self.character,
                struct.pack(">qb", 7, 3),
            )
        self.assertEqual(events, ["begin", "lock", "load", ("save", 3), "commit"])
        self.assertEqual(result["selected_slot"], 3)
