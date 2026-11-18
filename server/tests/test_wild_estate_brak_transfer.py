"""Focused source and transaction checks for Wild Estate 714 -> 723."""

import json
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

from wakfu_server import owned_story_generic_transfer as transfer
from wakfu_server import dungeon_runtime, dungeon_exit, owned_story_controller
from wakfu_server import owned_story_mechanics, owned_story_generic_entry


ROOT = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"
SOURCE = json.loads((ROOT / "wild-estate-brak-714.configuration.json").read_text())
DECLARATION = SOURCE["topology"]["owned_story_controller"]["generic_transfers"][0]
BODY = struct.pack(">qHH", DECLARATION["source_id"], 0, 0)


class WildEstateTransferTests(unittest.TestCase):
    def test_native_source_and_authored_prerequisite_are_exact(self):
        self.assertEqual(DECLARATION["target_route_key"], "quest-generic-723-20427-473")
        self.assertEqual(DECLARATION["requires"], ["brak-present-inscription"])
        self.assertEqual(transfer.selection(SOURCE, BODY), DECLARATION)
        with self.assertRaisesRegex(ValueError, "lost its native action"):
            transfer.selection(SOURCE, struct.pack(">qHH", 20427, 1, 0))
        self.assertIsNone(transfer.selection(SOURCE, struct.pack(">qHH", 20426, 0, 0)))
        with self.assertRaises(ValueError):
            transfer.selection(SOURCE, b"bad")

    def _case(self, completed):
        origin = dict(id=91, account_id=19, map_id=714, instance_id=501, x=9, y=-3, z=0)
        config = deepcopy(SOURCE)
        run = dict(party_id=701, instance_id=501)
        db_calls = []
        db = SimpleNamespace(
            execute=lambda sql, args=(): db_calls.append((sql, args)) or Cursor()
        )

        @contextmanager
        def connection():
            yield db

        store = SimpleNamespace(
            connection=connection,
            lock_character=lambda *_args, **_kwargs: None,
            character=lambda *_args, **_kwargs: dict(origin),
            now=lambda: 123456,
        )
        return origin, config, run, db, db_calls, store

    def test_missing_inscription_rejects_before_departure(self):
        origin, config, run, db, calls, store = self._case(set())
        with patch.object(
            dungeon_runtime, "configuration_for_instance", return_value=(run, config)
        ), patch.object(
            owned_story_controller,
            "_scope",
            return_value=(config["topology"]["owned_story_controller"], set()),
        ), patch.object(
            owned_story_controller, "pending_scene", return_value=None
        ), patch.object(
            dungeon_exit, "_leave"
        ) as leave:
            with self.assertRaisesRegex(ValueError, "genuine source steps"):
                transfer.enter(
                    store,
                    19,
                    "lease",
                    origin,
                    BODY,
                    loaded=True,
                    blocked=False,
                    allowed_position_accounts={19},
                )
        leave.assert_not_called()
        self.assertTrue(calls)

    def test_qualified_transfer_leaves_and_enters_in_one_database_transaction(self):
        origin, config, run, db, calls, store = self._case({"brak-present-inscription"})
        selected = config["topology"]["owned_story_controller"]
        order = []
        entered = dict(origin, map_id=723, instance_id=902, x=9, y=-3, z=0)

        def execute(sql, args=()):
            calls.append((sql, args))
            if "SELECT character_id FROM player_party_members" in sql:
                return Cursor(rows=[dict(character_id=91)])
            return Cursor()

        db.execute = execute

        def leave(*_args, **kwargs):
            self.assertIs(kwargs["_db"], db)
            order.append("leave")

        def enter(*_args, **kwargs):
            self.assertIs(kwargs["_db"], db)
            order.append("enter")
            return dict(instance_id=902)

        with patch.object(
            dungeon_runtime, "configuration_for_instance", return_value=(run, config)
        ), patch.object(
            owned_story_controller,
            "_scope",
            return_value=(selected, {"brak-present-inscription"}),
        ), patch.object(
            owned_story_controller, "pending_scene", return_value=None
        ), patch.object(
            owned_story_controller, "interact", return_value={"packets": [b"source"]}
        ), patch.object(
            owned_story_mechanics,
            "sources",
            return_value={"programs": {"20427": {"native": True}}},
        ), patch.object(
            owned_story_mechanics, "executor", return_value=lambda *_: None
        ), patch.object(
            owned_story_generic_entry,
            "configuration",
            return_value={
                "route": {
                    "key": DECLARATION["target_route_key"],
                    "native_generic_entry": {"program": {"native": True}},
                }
            },
        ), patch.object(
            owned_story_generic_entry,
            "validate_route",
            return_value=(
                dict(id=20427),
                None,
                None,
                dict(action_reference=473),
                dict(map_id=723),
                None,
            ),
        ), patch.object(
            dungeon_exit, "_leave", side_effect=leave
        ), patch.object(
            owned_story_generic_entry, "enter", side_effect=enter
        ), patch(
            "wakfu_server.companions.controlled_count", return_value=0
        ):
            result = transfer.enter(
                store,
                19,
                "lease",
                origin,
                BODY,
                loaded=True,
                blocked=False,
                allowed_position_accounts={19},
            )

        self.assertEqual(order, ["leave", "enter"])
        self.assertEqual(result["source_packets"], [b"source"])
        self.assertTrue(any("status='superseded'" in sql for sql, _ in calls))
        self.assertTrue(any("source_instance_id=%s" in sql for sql, _ in calls))


class Cursor:
    def __init__(self, row=None, rows=None):
        self.row, self.rows = row, list(rows or [])

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


if __name__ == "__main__":
    unittest.main()
