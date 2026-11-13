"""Durable combat mission receipt retry and replay behavior with an isolated fake DB."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from wakfu_server.achievements import combat_missions, rewards, storage, wire


class Cursor:
    def __init__(self, row=None, rows=()):
        self.row = row
        self.rows = list(rows)

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class ReceiptDB:
    def __init__(self):
        self.payload = None
        self.completed = None
        self.queries = []

    def execute(self, sql, args=()):
        self.queries.append((sql, args))
        if sql.startswith("INSERT INTO character_combat_mission_receipts"):
            self.payload = args[2].obj
            return Cursor({"fight_id": args[1]})
        if "FROM character_combat_mission_receipts" in sql:
            return Cursor(
                None
                if self.payload is None
                else {
                    "payload": self.payload,
                    "completed_at": self.completed,
                }
            )
        if "FROM character_combat_mission_counts" in sql:
            return Cursor(rows=[])
        if sql.startswith("UPDATE character_combat_mission_receipts"):
            self.completed = datetime.now(timezone.utc)
            return Cursor()
        return Cursor()


class CombatMissionReceiptTests(unittest.TestCase):
    def setUp(self):
        self.quest_id, self.objective_id = 71, 701
        self.rule = {
            "quest_id": self.quest_id,
            "objective_id": self.objective_id,
            "kind": "monster",
            "target_id": 900,
            "count": 1,
            "evidence": "source-backed boss objective",
        }
        self.definition = {
            "d": self.quest_id,
            "native_class": "aJM",
            "aqb": False,
            "cjI": {"always": True},
            "cjP": 1,
            "cjL": 0,
            "cjU": 0,
            "cjJ": [
                {
                    "d": self.objective_id,
                    "ckc": {"always": True},
                    "cke": {"always": True},
                }
            ],
            "cjK": [{"d": 44}],
        }
        self.event = {
            "fight_id": 33,
            "original_breeds": [900],
            "completed_dungeon_id": 88,
        }
        self.character = {"id": 4, "account_id": 5, "level": 100}
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [self.quest_id],
            "completed": [],
            "tracking": [self.quest_id],
            "recent": [],
            "completion_dates": {},
        }
        self.store = type(
            "Store",
            (),
            {
                "now": lambda _self: datetime(2026, 2, 20, 12, tzinfo=timezone.utc),
            },
        )()
        self.db = ReceiptDB()

    def test_no_publication_or_no_matching_rule_does_not_stage_receipt(self):
        with patch.object(combat_missions, "load", return_value=None):
            self.assertFalse(
                combat_missions.stage(self.db, self.store, self.character, self.event)
            )
        self.assertIsNone(self.db.payload)
        with patch.object(combat_missions, "load", return_value=([], {})):
            self.assertFalse(
                combat_missions.stage(self.db, self.store, self.character, self.event)
            )
        self.assertIsNone(self.db.payload)

    def test_failed_settlement_retries_from_immutable_receipt_and_completed_replay_is_noop(
        self,
    ):
        with patch.object(
            combat_missions,
            "load",
            return_value=([self.rule], {self.quest_id: self.definition}),
        ), patch.object(storage, "load_locked", return_value=self.state), patch(
            "wakfu_server.dungeon_criteria.evaluate", return_value=True
        ):
            self.assertTrue(
                combat_missions.stage(self.db, self.store, self.character, self.event)
            )
        self.assertEqual(self.event, self.db.payload["event"])
        self.assertEqual([self.rule], self.db.payload["rules"])

        after = {
            **self.state,
            "running": [],
            "completed": [self.quest_id],
            "objectives": [self.objective_id],
            "completion_dates": {str(self.quest_id): 1},
        }
        with patch.object(
            combat_missions, "load", side_effect=AssertionError("must use staged rules")
        ), patch.object(storage, "load_locked", return_value=self.state), patch.object(
            combat_missions,
            "advance",
            side_effect=[
                RuntimeError("transient"),
                (
                    after,
                    [(self.quest_id, {"d": 44})],
                    [self.objective_id],
                    [self.quest_id],
                    {self.objective_id: 1},
                ),
            ],
        ) as advance, patch.object(
            storage, "store"
        ) as save, patch.object(
            storage, "claim_reward"
        ) as claim, patch.object(
            rewards, "validate"
        ), patch.object(
            wire, "changes", return_value=[]
        ):
            with self.assertRaisesRegex(RuntimeError, "transient"):
                combat_missions.settle(self.db, self.store, self.character, self.event)
            self.assertIsNone(self.db.completed)
            packets = combat_missions.settle(
                self.db, self.store, self.character, self.event
            )
            self.assertEqual([], packets)
            advance.assert_called()
            self.assertEqual(2, advance.call_count)
            save.assert_called_once_with(self.db, self.character["id"], after)
            claim.assert_called_once_with(
                self.db, self.character["id"], self.quest_id, "once", 44, {"d": 44}
            )
            self.assertIsNotNone(self.db.completed)
            self.assertEqual(
                [],
                combat_missions.settle(self.db, self.store, self.character, self.event),
            )
            self.assertEqual(2, advance.call_count)
            self.assertEqual(1, claim.call_count)

    def test_staged_receipt_rejects_changed_event(self):
        self.db.payload = {
            "event": self.event,
            "rules": [self.rule],
            "definitions": {},
            "started": [],
            "occurred_at_ms": 1,
        }
        changed = {**self.event, "completed_dungeon_id": 99}
        with patch.object(storage, "load_locked", return_value=self.state):
            with self.assertRaisesRegex(ValueError, "does not match"):
                combat_missions.settle(self.db, self.store, self.character, changed)
