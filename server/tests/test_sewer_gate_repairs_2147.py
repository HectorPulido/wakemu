"""Exact native object bindings and immediate, once-only 2147 repair progress."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from wakfu_server import world_static
from wakfu_server.achievements import interactive_missions


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT / "wakfu_server/achievements/quest_interactions/astrub-sewer-gate-repairs.json"
)
NATIVE = ROOT / "tests/fixtures/native_mercenary_board_compiler.json"
EXPECTED = (
    (24124, 4258, (2, 37, 1)),
    (24123, 4259, (27, -28, 1)),
    (24125, 4260, (-43, 24, 1)),
    (24122, 4368, (-23, -47, 0)),
)


class _DB:
    def __init__(self, rows):
        self.rows = rows
        self.row = None

    def execute(self, _sql, params=()):
        self.row = self.rows.get(tuple(params))
        return self

    def fetchone(self):
        return self.row


class _Store:
    def __init__(self, rows, position):
        self.rows = rows
        self.position = position
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [2147],
            "completed": [],
            "tracking": [2147],
            "recent": [],
            "completion_dates": {},
            "active": [2147],
            "active_periods": {},
            "active_unknown": [],
        }
        self.receipts = set()
        self.completions = []

    @contextmanager
    def connection(self):
        yield _DB(self.rows)

    def character(self, account_id, character_id, _db):
        return {
            "id": character_id,
            "account_id": account_id,
            "level": 6,
            "effective_level": 6,
            **self.position,
        }

    def now(self):
        return datetime(2026, 11, 16, tzinfo=timezone.utc)


class SewerGateRepair2147Tests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text())
        fixture = json.loads(NATIVE.read_text())
        self.definition = next(
            row for row in fixture["additional_definitions"] if row["d"] == 2147
        )
        self.bindings = {}
        self.rows_by_object = {}
        for entry in self.manifest["bindings"]:
            row = {
                **entry,
                "revision": "native-2147-focused-test",
                "data": {"native": self.definition},
            }
            key = (
                entry["map_id"],
                entry["object_id"],
                entry["action_id"],
                entry["parameter"],
            )
            self.bindings[key] = row
            self.rows_by_object[entry["object_id"]] = row
        self.store = _Store(
            self.bindings,
            {"map_id": 546, "instance_id": 0, "x": -20, "y": 14, "z": 0},
        )

    def _native_object(self, _character, body):
        object_id, _action, _parameter = struct.unpack(">qHH", body)
        row = self.rows_by_object.get(object_id)
        if row is None:
            return {"type": "unknown", "x": 0, "y": 0, "z": 0}
        return {"type": row["object_type"], **{k: row[k] for k in ("x", "y", "z")}}

    def _record(self, _db, character_id, key, _payload):
        receipt = (character_id, key)
        if receipt in self.store.receipts:
            return False
        self.store.receipts.add(receipt)
        return True

    def _settle(
        self, _db, _store, character, _before, planned, _definitions, _links, *, now_ms
    ):
        after, intents, objectives, completed = planned
        self.store.state = deepcopy(after)
        self.store.completions.extend((character["id"], quest) for quest in completed)
        return {
            "state": after,
            "packets": [],
            "completed": completed,
            "new_objectives": objectives,
        }

    def _call(self, row, *, position=None, body=None):
        self.store.position = {
            "map_id": 546,
            "instance_id": 0,
            **(position or dict(zip(("x", "y", "z"), row["approach_cells"][:3]))),
        }
        location = {"id": 382, **self.store.position}
        return interactive_missions.interact(
            self.store,
            308,
            "generation-2147",
            location,
            body
            if body is not None
            else struct.pack(
                ">qHH", row["object_id"], row["action_id"], row["parameter"]
            ),
            loaded=True,
            blocked=False,
        )

    def _adapters(self):
        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(patch("wakfu_server.paid_containers._leased_owner"))
        stack.enter_context(patch("wakfu_server.environment_interactions._guard"))
        stack.enter_context(
            patch("wakfu_server.achievements.interactive_missions._owner")
        )
        stack.enter_context(
            patch(
                "wakfu_server.achievements.storage.load_locked",
                side_effect=lambda _db, _character_id: deepcopy(self.store.state),
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.achievements.storage.record_event",
                side_effect=self._record,
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.achievements.mission_dependencies.settle",
                side_effect=self._settle,
            )
        )
        stack.enter_context(
            patch(
                "wakfu_server.native_generic_rewards._payment",
                side_effect=lambda _db, _store, character, _policy: (character, [], []),
            )
        )
        stack.enter_context(
            patch.object(world_static, "interaction", side_effect=self._native_object)
        )
        return stack

    def test_four_exact_native_repairs_advance_immediately_and_replay_once(self):
        actual = tuple(
            (row["object_id"], row["objective_id"], tuple(row["approach_cells"][:3]))
            for row in self.manifest["bindings"]
        )
        self.assertEqual(EXPECTED, actual)
        self.assertTrue(
            all(
                row["map_id"] == 546
                and row["action_id"] == row["parameter"] == 0
                and row["required_item"]
                == row["required_quantity"]
                == row["script_id"]
                == 0
                for row in self.manifest["bindings"]
            )
        )

        with self._adapters():
            for index, row in enumerate(self.manifest["bindings"]):
                result = self._call(row)
                self.assertTrue(result["applied"])
                self.assertIn(row["objective_id"], self.store.state["objectives"])
                self.assertEqual(index < 3, 2147 in self.store.state["running"])
                receipt_count = len(self.store.receipts)
                replay = self._call(row)
                self.assertFalse(replay["applied"])
                self.assertEqual(receipt_count, len(self.store.receipts))

        self.assertIn(2147, self.store.state["completed"])
        self.assertEqual([4258, 4259, 4260, 4368], self.store.state["objectives"])
        self.assertEqual(4, len(self.store.receipts))
        self.assertEqual([(382, 2147)], self.store.completions)
        self.assertNotIn(
            2149, self.store.state["running"] + self.store.state["completed"]
        )
        self.assertFalse({2150, 2151}.intersection(self.store.state["running"]))

    def test_unassigned_and_wrong_source_requests_do_not_credit_a_repair(self):
        self.store.state["running"] = []
        self.store.state["active"] = []
        row = self.manifest["bindings"][0]
        initial = deepcopy(self.store.state)
        with self._adapters():
            result = self._call(row)
            self.assertFalse(result["applied"])
            with self.assertRaisesRegex(ValueError, "Unknown quest interaction"):
                self._call(row, body=struct.pack(">qHH", row["object_id"], 1, 0))
            with self.assertRaisesRegex(ValueError, "out of range"):
                self._call(row, position={"x": 3, "y": 37, "z": 1})
        self.assertEqual(initial, self.store.state)
        self.assertEqual(set(), self.store.receipts)
        self.assertNotIn(
            2149, self.store.state["running"] + self.store.state["completed"]
        )


if __name__ == "__main__":
    unittest.main()
