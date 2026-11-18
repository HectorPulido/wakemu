"""Focused producer checks for the native Temple decoration pickup."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_story_dynamic_pickups as pickups


PROFILE_DIR = (
    Path(__file__).parents[1] / "wakfu_server" / "maps" / "owned_story_profiles"
)


class _Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _DB:
    def __init__(self):
        self.publications = {}

    def execute(self, _sql, params):
        return _Result(self.publications.get(params[1]))


class OwnedStoryDynamicPickupTests(unittest.TestCase):
    def setUp(self):
        self.selected = json.loads((PROFILE_DIR / "wild-temple-718.json").read_text())
        self.row = json.loads(
            (PROFILE_DIR / "wild-temple-718.native.v1.json").read_text()
        )["reviewed_dynamic_pickups"][0]
        self.completed = {
            "gem-guardian-defeated",
            "first-temple-guardian-defeated",
            "artifact-passage-opened",
            "boss-key-collected",
            "relic-guardian-defeated",
        }
        self.character = dict(
            id=91, account_id=7, map_id=718, instance_id=9901, x=-15, y=59, z=-24
        )
        self.db = _DB()
        self.store = Mock()
        self.store.character.return_value = dict(self.character)
        self.store.now.return_value = datetime(2026, 11, 17, tzinfo=timezone.utc)
        self.events = {}

    def _scope(self, _db, _store, _character):
        return self.selected, self.completed

    def _record_event(self, _db, _character, key, payload):
        self.events[key] = payload
        if payload.get("step") == "artifact-taken":
            self.completed.add("artifact-taken")
        if key.startswith("owned-dynamic-pickup:"):
            self.db.publications[key] = {"payload": payload}
        return True

    @contextmanager
    def _run(self, *, capacity_error=False):
        with patch.object(
            pickups.controller, "_scope", side_effect=self._scope
        ), patch.object(
            pickups.storage,
            "load_locked",
            return_value={"running": {1684}, "objectives": set()},
        ), patch.object(
            pickups.storage, "record_event", side_effect=self._record_event
        ), patch(
            "wakfu_server.npc_actor_identity.allocate_block", return_value=8800123
        ), patch.object(
            pickups.mechanics, "executor", return_value=lambda *_args: []
        ), patch.object(
            pickups.rewards, "grant"
        ) as grant:
            if capacity_error:
                grant.side_effect = pickups.rewards.RewardCapacity("full")
            else:
                grant.return_value = [(12705, b"item-grant")]
            yield grant

    def test_actual_decoration_requires_prior_victory_owner_pose_and_awards_once(self):
        declaration = pickups.policy(self.selected)
        self.assertEqual(len(declaration), 1)
        self.assertEqual(
            (declaration[0]["item_reference"], declaration[0]["step_id"]),
            (17885, "artifact-taken"),
        )
        self.assertEqual(declaration[0]["position"], [-14, 59, -24])

        with self._run() as grant:
            published = pickups.packets(self.db, self.store, self.character)
            self.assertEqual([opcode for opcode, _ in published], [13664])
            key = f"owned-dynamic-pickup:{self.character['instance_id']}:bwork-artifact"
            uid = self.db.publications[key]["payload"]["uid"]
            body = __import__("struct").pack(">qHH", uid, 23, 0)
            result = pickups.interact(self.db, self.store, self.character, body)
            self.assertTrue(result["applied"])
            self.assertEqual(result["step"], "artifact-taken")
            self.assertEqual(result["packets"][0], (12705, b"item-grant"))
            grant.assert_called_once()

            replay = pickups.interact(self.db, self.store, self.character, body)
            self.assertFalse(replay["applied"])
            grant.assert_called_once()

            self.completed.discard("relic-guardian-defeated")
            self.completed.discard("artifact-taken")
            self.events.pop("owned-story:artifact-taken", None)
            locked = pickups.interact(self.db, self.store, self.character, body)
            self.assertFalse(locked["applied"])
            grant.assert_called_once()

            self.completed.add("relic-guardian-defeated")
            far = dict(self.character, x=-12)
            with self.assertRaisesRegex(ValueError, "adjacent approach"):
                pickups.interact(self.db, self.store, far, body)
            self.assertIsNone(
                pickups.interact(
                    self.db,
                    self.store,
                    self.character,
                    __import__("struct").pack(">qHH", uid + 1, 23, 0),
                )
            )
            with self.assertRaisesRegex(ValueError, "REPACK action"):
                pickups.interact(
                    self.db,
                    self.store,
                    self.character,
                    __import__("struct").pack(">qHH", uid, 22, 0),
                )
            wrong_owner = dict(self.character, id=92)
            with self.assertRaisesRegex(ValueError, "publication changed"):
                pickups.interact(self.db, self.store, wrong_owner, body)
            native_sources = self.selected["native_sources"]
            original_source_hash = native_sources["sha256"]
            native_sources["sha256"] = "f" * 64
            try:
                with self.assertRaises(ValueError):
                    pickups.interact(self.db, self.store, self.character, body)
            finally:
                native_sources["sha256"] = original_source_hash

    def test_capacity_failure_does_not_record_pickup_or_objective(self):
        with self._run(capacity_error=True) as grant:
            pickups.packets(self.db, self.store, self.character)
            key = f"owned-dynamic-pickup:{self.character['instance_id']}:bwork-artifact"
            uid = self.db.publications[key]["payload"]["uid"]
            with self.assertRaisesRegex(pickups.rewards.RewardCapacity, "full"):
                pickups.interact(
                    self.db,
                    self.store,
                    self.character,
                    __import__("struct").pack(">qHH", uid, 23, 0),
                )
            self.assertNotIn("artifact-taken", self.completed)
            self.assertFalse(
                any(
                    payload.get("step") == "artifact-taken"
                    for payload in self.events.values()
                )
            )
            grant.assert_called_once()


if __name__ == "__main__":
    unittest.main()
