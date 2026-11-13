"""Transaction-shaped Doby 1215 recurring delivery regression coverage."""
import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import recurring_turnin


CONTRACT = (
    Path(__file__).parents[1]
    / "wakfu_server/maps/native_quest_conversation_contracts.json"
)


class Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class CycleDB:
    """Small transactional projection for the recurring cycle receipt table."""

    def __init__(self):
        self.receipt = None
        self.statements = []

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        if "SELECT cycle_index,completed_at_ms" in sql:
            return Cursor(copy.deepcopy(self.receipt))
        if "INSERT INTO character_recurring_mission_cycles" in sql:
            character_id, quest_id, cycle, accepted_at = params
            self.receipt = {
                "character_id": character_id,
                "definition_id": quest_id,
                "cycle_index": cycle,
                "accepted_at_ms": accepted_at,
                "completed_at_ms": None,
            }
        elif "UPDATE character_recurring_mission_cycles SET completed_at_ms" in sql:
            completed_at, _character_id, _quest_id, cycle = params
            if self.receipt and self.receipt["cycle_index"] == cycle:
                self.receipt["completed_at_ms"] = completed_at
        return Cursor()


class MutableStore:
    def __init__(self, now_ms):
        self.now_ms = now_ms

    def now(self):
        return datetime.fromtimestamp(self.now_ms / 1000, timezone.utc)


class DobyRecurringTurnInTest(unittest.TestCase):
    def setUp(self):
        document = json.loads(CONTRACT.read_text())
        self.config = next(
            c for c in document["recurring_deliveries"] if c["quest_id"] == 1215
        )
        self.definition = next(d for d in document["definitions"] if d["d"] == 1215)
        self.character = {"id": 7, "account_id": 9, "level": 200}
        self.anchor = self.definition["cjT"]
        self.db = CycleDB()
        self.store = MutableStore(self.anchor + 1000)
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [],
            "completed": [],
            "tracking": [],
            "completion_dates": {},
            "recent": [],
        }

    def _run(self, operation, *args, **kwargs):
        """Supply a shared state view while preserving method call ordering."""
        from wakfu_server.achievements import storage

        with patch.object(
            storage,
            "load_locked",
            side_effect=lambda _db, _cid: copy.deepcopy(self.state),
        ), patch.object(
            storage,
            "store",
            side_effect=lambda _db, _cid, state: setattr(
                self, "state", copy.deepcopy(state)
            ),
        ):
            return operation(self.db, self.store, self.character, *args, **kwargs)

    def test_new_cycle_emits_reset_then_activation_after_previous_completion(self):
        from wakfu_server.achievements import storage

        self.db.receipt = {"cycle_index": 0, "completed_at_ms": self.anchor + 5000}
        self.state["completed"] = [1215]
        self.state["objectives"] = [2176]
        self.store.now_ms = self.anchor + 86_400_000 + 1000
        with patch(
            "wakfu_server.dungeon_achievement_authority.queries_from_snapshot",
            return_value={},
        ), patch(
            "wakfu_server.dungeon_criteria.evaluate", return_value=True
        ), patch.object(
            storage, "record_event", return_value=True
        ):
            packets = self._run(recurring_turnin.accept, self.definition, self.config)
        self.assertEqual([packet[0] for packet in packets], [13205, 13312, 13371])
        self.assertEqual(self.state["running"], [1215])
        self.assertEqual(self.state["completed"], [])

    def test_accept_pay_exact_five_once_complete_reward_replay_and_next_cycle_reset(
        self,
    ):
        from wakfu_server.achievements import storage

        rewards_delivered = []
        with patch(
            "wakfu_server.dungeon_achievement_authority.queries_from_snapshot",
            return_value={},
        ), patch(
            "wakfu_server.dungeon_criteria.evaluate", return_value=True
        ), patch.object(
            storage, "record_event", return_value=True
        ) as event, patch.object(
            storage,
            "claim_reward",
            side_effect=lambda *args: rewards_delivered.append(args),
        ), patch.object(
            recurring_turnin.wire, "changes", return_value=[(2, b"quest")]
        ), patch(
            "wakfu_server.achievements.service.drain_rewards",
            return_value=[(3, b"reward")],
        ):
            accepted = self._run(recurring_turnin.accept, self.definition, self.config)
            self.assertTrue(self.db.receipt)
            self.assertEqual(self.db.receipt["cycle_index"], 0)
            self.assertIn(1215, self.state["running"])
            self.assertIn(1215, self.state["tracking"])

            with patch(
                "wakfu_server.native_generic_rewards._payment",
                side_effect=ValueError("insufficient items"),
            ) as payment, patch.object(storage, "store") as store, patch.object(
                storage, "record_event"
            ) as no_receipt:
                state_before = copy.deepcopy(self.state)
                receipt_before = copy.deepcopy(self.db.receipt)
                with self.assertRaisesRegex(ValueError, "insufficient items"):
                    self._run(recurring_turnin.deliver, self.definition, self.config)
                self.assertEqual(self.state, state_before)
                self.assertEqual(self.db.receipt, receipt_before)
                payment.assert_called_once_with(
                    self.db,
                    self.store,
                    self.character,
                    {"group_cod": 15983, "group_coe": 5},
                )
                store.assert_not_called()
                no_receipt.assert_not_called()

            with patch(
                "wakfu_server.native_generic_rewards._payment",
                return_value=({}, [(1, b"paid")], []),
            ) as payment:
                delivered = self._run(
                    recurring_turnin.deliver, self.definition, self.config
                )
                self.assertTrue(delivered["applied"])
                self.assertEqual(delivered["completed"], [1215])
                self.assertEqual(
                    delivered["packets"], [(1, b"paid"), (2, b"quest"), (3, b"reward")]
                )
                payment.assert_called_once_with(
                    self.db,
                    self.store,
                    self.character,
                    {"group_cod": 15983, "group_coe": 5},
                )
            self.assertEqual(self.db.receipt["completed_at_ms"], self.store.now_ms)
            self.assertIn(1215, self.state["completed"])
            self.assertEqual(len(rewards_delivered), 1)
            event.assert_any_call(
                self.db,
                7,
                "recurring-dialogue:1215:0:deliver",
                {
                    "kind": "reconstructed_recurring_dialogue_delivery_v1",
                    "quest_id": 1215,
                    "objective_id": 2176,
                    "cycle": 0,
                    "item_reference": 15983,
                    "item_quantity": 5,
                },
            )

            with patch("wakfu_server.native_generic_rewards._payment") as payment:
                replay = self._run(
                    recurring_turnin.deliver, self.definition, self.config
                )
                self.assertFalse(replay["applied"])
                payment.assert_not_called()
            self.assertEqual(len(rewards_delivered), 1)

            # After the configured 24-hour boundary, acceptance resets only
            # this mission's objective/completion projection and opens cycle 1.
            self.store.now_ms = self.anchor + 86_400_000 + 1000
            reset_packets = self._run(
                recurring_turnin.accept, self.definition, self.config
            )
            self.assertEqual(self.db.receipt["cycle_index"], 1)
            self.assertIsNone(self.db.receipt["completed_at_ms"])
            self.assertIn(1215, self.state["running"])
            self.assertNotIn(1215, self.state["completed"])
            self.assertNotIn(2176, self.state["objectives"])
            self.assertNotIn("1215", self.state["completion_dates"])
            self.assertIn(1215, self.state["tracking"])
            self.assertTrue(reset_packets)


if __name__ == "__main__":
    unittest.main()
