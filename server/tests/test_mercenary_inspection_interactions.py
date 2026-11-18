"""Four authenticated native 2144 inspection interactions advance once each."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

from wakfu_server.achievements import interactive_missions


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT
    / "wakfu_server/achievements/quest_interactions/astrub-mercenary-inspections.json"
)
FIXTURE = ROOT / "tests/fixtures/native_mercenary_inspection_2144.json"


class FakeDB:
    def __init__(self, bindings):
        self.bindings = bindings
        self.row = None

    def execute(self, _sql, params=()):
        map_id, object_id, action_id, parameter = params
        self.row = self.bindings.get((map_id, object_id, action_id, parameter))
        return self

    def fetchone(self):
        return self.row


class FakeStore:
    def __init__(self, rows, location):
        self.rows = rows
        self.location = location
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [2144],
            "completed": [],
            "tracking": [2144],
            "recent": [],
            "completion_dates": {},
            "active": [2144],
            "active_periods": {},
            "active_unknown": [],
        }
        self.receipts = set()
        self.claimed = []

    @contextmanager
    def connection(self):
        yield FakeDB(self.rows)

    def character(self, account_id, character_id, _db):
        return {
            "id": character_id,
            "account_id": account_id,
            "level": 6,
            "effective_level": 6,
            **self.location,
        }

    def now(self):
        return datetime(2026, 11, 15, tzinfo=timezone.utc)


def fixture():
    manifest = json.loads(MANIFEST.read_text())
    definition = json.loads(FIXTURE.read_text())["definition"]
    bindings = {}
    for entry in manifest["bindings"]:
        row = {
            **entry,
            "revision": "native-2144-reviewed-test",
            "data": {"native": definition},
        }
        bindings[
            (
                entry["map_id"],
                entry["object_id"],
                entry["action_id"],
                entry["parameter"],
            )
        ] = row
    return manifest, definition, bindings


class MercenaryInspectionInteractionTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.definition, self.bindings = fixture()
        self.rows_by_object = {row["object_id"]: row for row in self.bindings.values()}
        self.store = FakeStore(
            self.bindings,
            {"map_id": 527, "instance_id": 0, "x": 73, "y": -1, "z": 0},
        )

        def native_interaction(_character, body):
            object_id, _action, _parameter = struct.unpack(">qHH", body)
            row = self.rows_by_object.get(object_id)
            if row is None:
                return {"type": "unknown", "x": 0, "y": 0, "z": 0}
            return {
                "type": row["object_type"],
                **{key: row[key] for key in ("x", "y", "z")},
            }

        self.interaction_patch = patch.dict(
            sys.modules,
            {
                "wakfu_server.world_static": types.SimpleNamespace(
                    interaction=native_interaction
                )
            },
        )
        self.interaction_patch.start()
        self.addCleanup(self.interaction_patch.stop)

    def record_event(self, _db, character_id, key, _payload):
        receipt = (character_id, key)
        if receipt in self.store.receipts:
            return False
        self.store.receipts.add(receipt)
        return True

    def settle(
        self, _db, _store, character, _before, planned, _definitions, _links, *, now_ms
    ):
        after, intents, objectives, completed = planned
        self.store.state = deepcopy(after)
        self.store.claimed.extend(
            (character["id"], quest, reward["d"]) for quest, reward in intents
        )
        return {
            "state": after,
            "packets": [],
            "completed": completed,
            "new_objectives": objectives,
        }

    def call(self, row, *, position=None, body=None):
        self.store.location = {
            "map_id": 527,
            "instance_id": 0,
            **(
                position
                or {
                    "x": row["approach_cells"][3],
                    "y": row["approach_cells"][4],
                    "z": row["approach_cells"][5],
                }
            ),
        }

        location = {"id": 88, **self.store.location}
        return interactive_missions.interact(
            self.store,
            88,
            "generation-88",
            location,
            body
            or struct.pack(
                ">qHH", row["object_id"], row["action_id"], row["parameter"]
            ),
            loaded=True,
            blocked=False,
        )

    def test_four_native_objects_advance_immediately_and_complete_once(self):
        claimed_before = list(self.store.claimed)
        with patch("wakfu_server.paid_containers._leased_owner"), patch(
            "wakfu_server.environment_interactions._guard"
        ), patch("wakfu_server.achievements.interactive_missions._owner"), patch(
            "wakfu_server.achievements.storage.load_locked",
            side_effect=lambda _db, _character_id: deepcopy(self.store.state),
        ), patch(
            "wakfu_server.achievements.storage.record_event",
            side_effect=self.record_event,
        ), patch(
            "wakfu_server.achievements.mission_dependencies.settle",
            side_effect=self.settle,
        ), patch(
            "wakfu_server.native_generic_rewards._payment",
            side_effect=lambda _db, store, character, _policy: (character, [], []),
        ):
            for index, row in enumerate(self.bindings.values()):
                result = self.call(row)
                self.assertTrue(result["applied"])
                objective_id = row["objective_id"]
                self.assertIn(objective_id, self.store.state["objectives"])
                self.assertEqual(index < 3, 2144 in self.store.state["running"])
                receipt_count = len(self.store.receipts)
                replay = self.call(row)
                self.assertFalse(replay["applied"])
                self.assertEqual(receipt_count, len(self.store.receipts))
            self.assertIn(2144, self.store.state["completed"])
            self.assertEqual([4246, 4247, 4248, 4249], self.store.state["objectives"])
            self.assertEqual(
                [(88, 2144, 3691), (88, 2144, 4655)],
                self.store.claimed[len(claimed_before) :],
            )
            self.assertEqual(4, len(self.store.receipts))

    def test_wrong_object_action_parameter_and_stale_approach_do_not_progress(self):
        row = next(iter(self.bindings.values()))
        initial = deepcopy(self.store.state)
        wrong_requests = (
            struct.pack(">qHH", 99999, 0, 0),
            struct.pack(">qHH", row["object_id"], 1, 0),
            struct.pack(">qHH", row["object_id"], 0, 1),
        )
        with patch("wakfu_server.paid_containers._leased_owner"), patch(
            "wakfu_server.environment_interactions._guard"
        ), patch("wakfu_server.achievements.interactive_missions._owner"), patch(
            "wakfu_server.achievements.storage.load_locked",
            side_effect=lambda _db, _character_id: deepcopy(self.store.state),
        ):
            for body in wrong_requests:
                with self.assertRaisesRegex(ValueError, "Unknown quest interaction"):
                    self.call(row, body=body)
            with self.assertRaisesRegex(ValueError, "out of range"):
                self.call(row, position={"x": 74, "y": -1, "z": 0})
        self.assertEqual(initial, self.store.state)
        self.assertEqual(set(), self.store.receipts)
        self.assertEqual([], self.store.claimed)


if __name__ == "__main__":
    unittest.main()
